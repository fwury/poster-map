"""Turn raw OSM features into projected, clipped, styled-ready geometry layers."""
from __future__ import annotations

import math

from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import linemerge, polygonize, unary_union

from .geo import Projection

GREEN = {
    "leisure": {"park", "garden", "nature_reserve", "golf_course", "common", "recreation_ground",
                "dog_park"},
    "landuse": {"grass", "forest", "meadow", "recreation_ground", "cemetery", "village_green",
                "park"},
    "natural": {"wood", "scrub", "grassland", "heath", "wetland"},
}
WATER = {
    "natural": {"water", "bay"},
    "waterway": {"riverbank", "dock"},
    "landuse": {"reservoir", "basin"},
}
TUNNEL = {"yes", "culvert", "flooded"}


def _match(tags, table) -> bool:
    return any(tags.get(k) in vals for k, vals in table.items())


def _is_hidden(tags) -> bool:
    return tags.get("tunnel") in TUNNEL or tags.get("location") == "underground"


class LayerBuilder:
    def __init__(self, cfg: dict, proj: Projection, half_w: float, half_h: float,
                 scale_pt_per_m: float, log=print):
        self.cfg = cfg
        self.proj = proj
        self.half_w, self.half_h = half_w, half_h
        self.scale = scale_pt_per_m
        self.rot = float(cfg["area"].get("rotation_deg") or 0)
        self.log = log
        # Visual simplification tolerance: 0.15 pt on paper is invisible.
        self.tol = 0.15 / scale_pt_per_m
        pad = 0.02 * max(half_w, half_h)
        self.window = box(-half_w - pad, -half_h - pad, half_w + pad, half_h + pad)
        self.tier_of = {}
        for name, tier in cfg["roads"]["tiers"].items():
            if tier.get("enabled", True):
                for hw in tier.get("highway", []):
                    self.tier_of[hw] = name

    # -- geometry helpers --------------------------------------------------
    def _xy(self, coords):
        f = self.proj.fwd
        pts = [f(lon, lat) for lon, lat in coords]
        if self.rot:
            a = math.radians(self.rot)
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x * ca + y * sa, -x * sa + y * ca) for x, y in pts]  # clockwise map rotation
        return pts

    def _line(self, f):
        return LineString(self._xy(f["g"])) if len(f["g"]) >= 2 else None

    def _area(self, f):
        if f["k"] == "L":
            g = f["g"]
            if len(g) < 4 or g[0] != g[-1]:
                return None
            poly = Polygon(self._xy(g))
        else:
            polys = []
            for outer, inners in f["g"]:
                if len(outer) >= 4:
                    polys.append(Polygon(self._xy(outer),
                                         [self._xy(r) for r in inners if len(r) >= 4]))
            poly = MultiPolygon(polys) if len(polys) > 1 else (polys[0] if polys else None)
        if poly is None:
            return None
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly

    def _clip(self, geom):
        if geom is None or geom.is_empty:
            return None
        minx, miny, maxx, maxy = self.window.bounds
        b = geom.bounds
        if b[2] < minx or b[0] > maxx or b[3] < miny or b[1] > maxy:
            return None
        if not (minx <= b[0] and b[2] <= maxx and miny <= b[1] and b[3] <= maxy):
            geom = geom.intersection(self.window)
        return None if geom.is_empty else geom

    # -- main ----------------------------------------------------------------
    def build(self, feats) -> dict:
        cfg = self.cfg
        lay = cfg["layers"]
        skip_tunnels = cfg["data"].get("skip_tunnels", True)
        rail_types = set(cfg["rail"]["types"])
        ww_widths = cfg["waterways"]["widths"]

        water, green, buildings, coast = [], [], [], []
        partial = {}  # relation id -> member lines of unassembled water relations
        rail, waterways = [], {k: [] for k in ww_widths}
        roads = {name: [] for name in cfg["roads"]["tiers"]}

        for f in feats:
            t = f["t"]
            if skip_tunnels and _is_hidden(t):
                continue
            if f["k"] == "M":
                g = self._line(f)
                if g is not None:
                    partial.setdefault(f["r"], []).append(g)
                continue
            if t.get("natural") == "coastline" and f["k"] == "L":
                g = self._line(f)
                if g is not None:
                    coast.append(g)
                continue
            if lay.get("water") and _match(t, WATER):
                g = self._clip(self._area(f))
                if g is not None:
                    water.append(g)
                continue
            if lay.get("green") and _match(t, GREEN):
                g = self._clip(self._area(f))
                if g is not None:
                    green.append(g)
                continue
            if lay.get("buildings") and t.get("building") not in (None, "no"):
                g = self._clip(self._area(f))
                if g is not None:
                    buildings.append(g)
                continue
            if f["k"] != "L":
                continue
            hw = t.get("highway")
            if hw and lay.get("roads") and hw in self.tier_of and t.get("area") != "yes":
                g = self._clip(self._line(f))
                if g is not None:
                    roads[self.tier_of[hw]].append(g)
                continue
            if lay.get("rail") and t.get("railway") in rail_types:
                g = self._clip(self._line(f))
                if g is not None:
                    rail.append(g)
                continue
            ww = t.get("waterway")
            if lay.get("waterways") and ww in waterways:
                g = self._clip(self._line(f))
                if g is not None:
                    waterways[ww].append(g)

        out = {}
        if lay.get("water"):
            sea = self._sea_from_coastline(coast)
            if sea is not None:
                water.append(sea)
            road_lines = [g for v in roads.values() for g in v]
            for rid, lines in partial.items():
                w = self._water_from_partial_relation(lines, road_lines)
                if w is not None:
                    water.append(w)
            out["water"] = self._union_simplify(water)
        if lay.get("green"):
            g = self._union_simplify(green)
            # Parks drawn over water would hide shorelines; keep water on top.
            out["green"] = g
        if lay.get("buildings"):
            out["buildings"] = self._union_simplify(buildings)
        out["waterways"] = {k: self._merge_lines(v) for k, v in waterways.items() if v}
        out["rail"] = self._merge_lines(rail)
        out["roads"] = {k: self._merge_lines(v) for k, v in roads.items() if v}
        n_roads = sum(len(v) for v in roads.values())
        self.log(f"  roads: {n_roads:,} segments in {len(out['roads'])} tiers; "
                 f"water polys: {len(water)}; green polys: {len(green)}; coastline ways: {len(coast)}")
        return out

    def _union_simplify(self, geoms):
        if not geoms:
            return None
        u = unary_union([g for g in geoms if g.geom_type in ("Polygon", "MultiPolygon")
                         or g.geom_type == "GeometryCollection"])
        u = u.simplify(self.tol, preserve_topology=True)
        return None if u.is_empty else u

    def _merge_lines(self, lines):
        if not lines:
            return None
        parts = []
        for g in lines:
            if g.geom_type == "LineString":
                parts.append(g)
            elif hasattr(g, "geoms"):
                parts.extend(x for x in g.geoms if x.geom_type == "LineString")
        merged = linemerge(parts) if parts else None
        if merged is None or merged.is_empty:
            return None
        return merged.simplify(self.tol, preserve_topology=False)

    def _water_from_partial_relation(self, lines, road_lines):
        """Water polygon for a lake/river relation only partly present in the data.

        The relation's member ways are boundaries between water and land, so the
        faces they cut the frame into alternate water/land.  Two-colour the faces,
        then call the colour class with (far) fewer roads per km² "water".
        """
        frame = self.window
        clipped = [g for g in (self._clip(l) for l in lines) if g is not None]
        if not clipped:
            return None
        faces = list(polygonize(unary_union([frame.exterior] + clipped)))
        if len(faces) < 2:
            return None
        colors = _two_color(faces)
        roads = unary_union(road_lines) if road_lines else None
        density = []
        for c in (0, 1):
            group = unary_union([f for f, k in zip(faces, colors) if k == c])
            length = roads.intersection(group).length if roads is not None else 0.0
            density.append(length / max(group.area, 1.0))
        water_color = 0 if density[0] < density[1] else 1
        return unary_union([f for f, k in zip(faces, colors) if k == water_color])

    def _sea_from_coastline(self, coast):
        """OSM coastlines have land on the left, water on the right.

        Split the (slightly enlarged) frame by the coastline ways and keep
        the faces that sit on the water side.
        """
        if not coast:
            return None
        frame = self.window
        lines = [g for g in (self._clip(c) for c in coast) if g is not None]
        if not lines:
            return None
        noded = unary_union([frame.exterior] + lines)
        faces = list(polygonize(noded))
        if len(faces) < 2:
            return None
        d = max(self.tol * 4, 1.0)
        right = unary_union([c.buffer(-d, single_sided=True) for c in coast
                             if c.intersects(frame)])
        left = unary_union([c.buffer(d, single_sided=True) for c in coast
                            if c.intersects(frame)])
        sea = []
        for face in faces:
            wa = face.intersection(right).area
            la = face.intersection(left).area
            if wa > la:
                sea.append(face)
        if not sea:
            return None
        return unary_union(sea)


def _two_color(faces):
    """Colour polygon faces 0/1 so that faces sharing an edge get different colours."""
    from shapely.strtree import STRtree

    tree = STRtree(faces)
    color = [None] * len(faces)
    for start in range(len(faces)):
        if color[start] is not None:
            continue
        color[start] = 0
        stack = [start]
        while stack:
            i = stack.pop()
            for j in tree.query(faces[i]):
                j = int(j)
                if j == i:
                    continue
                shared = faces[i].boundary.intersection(faces[j].boundary)
                if shared.is_empty or shared.length <= 0:
                    continue  # touch at a point only
                if color[j] is None:
                    color[j] = 1 - color[i]
                    stack.append(j)
    return color


def frame_rotation_extent(half_w, half_h, rot_deg):
    """Half-extents of the axis-aligned box covering a rotated frame."""
    a = math.radians(rot_deg)
    ca, sa = abs(math.cos(a)), abs(math.sin(a))
    return half_w * ca + half_h * sa, half_w * sa + half_h * ca

