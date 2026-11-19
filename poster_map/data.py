"""Fetch OpenStreetMap features (Overpass API or a local .osm.pbf) with caching.

Features are kept in a source-neutral raw form so that styling/classification
can change without re-downloading:

    {"t": {tag: value}, "k": "L", "g": [(lon, lat), ...]}                # way
    {"t": {...},        "k": "A", "g": [[outer, [inner, ...]], ...]}       # multipolygon relation
    {"t": {...},        "k": "M", "g": [(lon, lat), ...], "r": rel_id}     # member way of a water
                                                                            # relation that could not
                                                                            # be assembled (e.g. a
                                                                            # lake cut by the extract)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import pickle
import time
from pathlib import Path

import requests
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from .geo import UA

SCHEMA = 2  # bump when the raw feature format changes (invalidates caches)

KEEP_KEYS = ("highway", "railway", "waterway", "natural", "landuse", "leisure", "building",
             "tunnel", "area", "water", "layer", "covered", "location", "service")


def _tags(raw) -> dict:
    return {k: raw[k] for k in KEEP_KEYS if k in raw}


def _is_water_tags(t) -> bool:
    return (t.get("natural") in ("water", "bay") or t.get("waterway") in ("riverbank", "dock")
            or t.get("landuse") in ("reservoir", "basin"))


def _bbox_contains(outer, inner) -> bool:
    s, w, n, e = outer
    s2, w2, n2, e2 = inner
    return s <= s2 and w <= w2 and n >= n2 and e >= e2


# --------------------------------------------------------------------------- cache
class Cache:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.index = json.loads(self.index_path.read_text()) if self.index_path.exists() else []

    def find(self, source_id: str, bbox, buildings: bool):
        for entry in self.index:
            if (entry["source"] == source_id and _bbox_contains(entry["bbox"], bbox)
                    and (entry["buildings"] or not buildings)
                    and (self.root / entry["file"]).exists()):
                with gzip.open(self.root / entry["file"], "rb") as f:
                    return pickle.load(f)
        return None

    def store(self, source_id: str, bbox, buildings: bool, feats):
        name = hashlib.sha1(f"{source_id}{bbox}{buildings}".encode()).hexdigest()[:16] + ".pkl.gz"
        with gzip.open(self.root / name, "wb") as f:
            pickle.dump(feats, f, protocol=pickle.HIGHEST_PROTOCOL)
        self.index = [e for e in self.index if e["file"] != name]
        self.index.append({"source": source_id, "bbox": list(bbox), "buildings": buildings,
                           "file": name, "count": len(feats)})
        self.index_path.write_text(json.dumps(self.index, indent=1))


# --------------------------------------------------------------------------- overpass
def _overpass_query(bbox, buildings: bool) -> str:
    s, w, n, e = bbox
    b = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
    parts = [
        f'way["highway"]{b};',
        f'way["railway"]{b};',
        f'way["waterway"]{b};',
        f'way["natural"~"^(water|coastline|wood|scrub|grassland|heath|bay|wetland|beach|sand)$"]{b};',
        f'rel["natural"~"^(water|wood|scrub|grassland|heath|bay|wetland|beach|sand)$"]{b};',
        f'way["landuse"]{b};', f'rel["landuse"]{b};',
        f'way["leisure"]{b};', f'rel["leisure"]{b};',
        f'rel["waterway"]{b};', f'rel["water"]{b};',
    ]
    if buildings:
        parts += [f'way["building"]{b};', f'rel["building"]{b};']
    return "[out:json][timeout:300][maxsize:1073741824];(" + "".join(parts) + ");out tags geom qt;"


def _assemble_relation(members) -> list:
    """Overpass `out geom` relation members → [[outer, [inners]], ...] in lon/lat."""
    outer_lines, inner_lines = [], []
    for m in members:
        if m.get("type") != "way" or not m.get("geometry"):
            continue
        coords = [(p["lon"], p["lat"]) for p in m["geometry"] if p]
        if len(coords) < 2:
            continue
        (inner_lines if m.get("role") == "inner" else outer_lines).append(LineString(coords))
    outers = list(polygonize(unary_union(outer_lines))) if outer_lines else []
    if not outers:
        return []
    shape = unary_union(outers)
    if inner_lines:
        inners = list(polygonize(unary_union(inner_lines)))
        if inners:
            shape = shape.difference(unary_union(inners))
    polys = getattr(shape, "geoms", [shape])
    return [[list(p.exterior.coords), [list(r.coords) for r in p.interiors]]
            for p in polys if isinstance(p, Polygon) and not p.is_empty]


def fetch_overpass(urls, bbox, buildings: bool, log=print) -> list:
    query = _overpass_query(bbox, buildings)
    last_err = None
    for attempt in range(2):
        for url in urls:
            try:
                log(f"  querying {url} …")
                r = requests.post(url, data={"data": query}, headers={"User-Agent": UA},
                                  timeout=360)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                elements = r.json()["elements"]
                break
            except Exception as exc:  # try the next mirror
                last_err = exc
                log(f"    failed: {exc}")
        else:
            time.sleep(5 * (attempt + 1))
            continue
        break
    else:
        raise RuntimeError(f"All Overpass endpoints failed ({last_err}). "
                           "Try `data.source: pbf` with a downloaded extract.")

    feats = []
    for el in elements:
        tags = _tags(el.get("tags", {}))
        if not tags:
            continue
        if el["type"] == "way" and el.get("geometry"):
            feats.append({"t": tags, "k": "L",
                          "g": [(p["lon"], p["lat"]) for p in el["geometry"]]})
        elif el["type"] == "relation":
            polys = _assemble_relation(el.get("members", []))
            if polys:
                feats.append({"t": tags, "k": "A", "g": polys})
            elif _is_water_tags(tags):
                for m in el.get("members", []):
                    if m.get("type") == "way" and m.get("geometry"):
                        feats.append({"t": tags, "k": "M", "r": el["id"],
                                      "g": [(p["lon"], p["lat"]) for p in m["geometry"] if p]})
    return feats


# --------------------------------------------------------------------------- pbf
def _ensure_local_pbf(spec: str, cache_dir: str, config_dir: str | None, log=print) -> Path:
    if spec.startswith(("http://", "https://")):
        dest = Path(cache_dir) / spec.rstrip("/").split("/")[-1]
        if not dest.exists():
            log(f"  downloading {spec} …")
            with requests.get(spec, stream=True, headers={"User-Agent": UA}, timeout=600) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
        return dest
    p = Path(spec)
    if not p.is_absolute() and not p.exists() and config_dir:
        p = Path(config_dir) / p
    if not p.exists():
        raise FileNotFoundError(spec)
    return p


def fetch_pbf(path: Path, bbox, buildings: bool, log=print) -> list:
    import osmium  # optional dependency

    s, w, n, e = bbox
    keys = ["highway", "railway", "waterway", "natural", "landuse", "leisure"]
    if buildings:
        keys.append("building")

    def inside(lon, lat):
        return w <= lon <= e and s <= lat <= n

    # Pass 1: water relations and their member way ids.
    water_rels, member_of = {}, {}
    for rel in (osmium.FileProcessor(str(path), osmium.osm.RELATION)
                .with_filter(osmium.filter.KeyFilter("natural", "waterway", "landuse", "water"))):
        tags = _tags(rel.tags)
        if _is_water_tags(tags):
            water_rels[rel.id] = tags
            for m in rel.members:
                if m.type == "w":
                    member_of.setdefault(m.ref, []).append(rel.id)

    feats = []
    assembled = set()
    fp = (osmium.FileProcessor(str(path))
          .with_locations()
          .with_areas()
          .with_filter(osmium.filter.KeyFilter(*keys)))
    for obj in fp:
        if obj.is_way():
            try:
                coords = [(nd.lon, nd.lat) for nd in obj.nodes]
            except Exception:  # missing node locations at the extract edge
                coords = [(nd.lon, nd.lat) for nd in obj.nodes if nd.location.valid()]
            if len(coords) < 2:
                continue
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            if max(xs) < w or min(xs) > e or max(ys) < s or min(ys) > n:
                continue
            tags = _tags(obj.tags)
            if tags:
                feats.append({"t": tags, "k": "L", "g": coords})
        elif obj.is_area() and not obj.from_way():
            polys = []
            hit = False
            for outer in obj.outer_rings():
                oc = [(nd.lon, nd.lat) for nd in outer]
                hit = hit or any(inside(*c) for c in oc[:: max(1, len(oc) // 64)])
                inners = [[(nd.lon, nd.lat) for nd in inner] for inner in obj.inner_rings(outer)]
                polys.append([oc, inners])
            if polys:
                xs = [c[0] for p in polys for c in p[0]]
                ys = [c[1] for p in polys for c in p[0]]
                if max(xs) < w or min(xs) > e or max(ys) < s or min(ys) > n:
                    continue
                tags = _tags(obj.tags)
                if tags:
                    feats.append({"t": tags, "k": "A", "g": polys})
                    assembled.add(obj.orig_id())

    # Pass 2: member ways of water relations that osmium couldn't assemble
    # (typically big lakes that extend past the extract boundary).
    missing = {wid for wid, rels in member_of.items()
               if any(r not in assembled for r in rels)}
    if missing:
        for way in (osmium.FileProcessor(str(path), osmium.osm.NODE | osmium.osm.WAY)
                    .with_locations()
                    .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
                    .with_filter(osmium.filter.IdFilter(missing))):
            coords = [(nd.lon, nd.lat) for nd in way.nodes if nd.location.valid()]
            if len(coords) < 2:
                continue
            for rid in member_of[way.id]:
                if rid not in assembled:
                    feats.append({"t": water_rels[rid], "k": "M", "r": rid, "g": coords})
        log(f"  partial water relations: {len({r for w in missing for r in member_of[w]} - assembled)}")
    return feats


# --------------------------------------------------------------------------- entry
def get_features(cfg: dict, bbox, buildings: bool, log=print) -> list:
    d = cfg["data"]
    cache = Cache(d["cache_dir"])
    if d["source"] == "pbf":
        if not d.get("pbf"):
            raise ValueError("data.source is 'pbf' but data.pbf is not set")
        path = _ensure_local_pbf(d["pbf"], d["cache_dir"], cfg.get("_config_dir"), log)
        st = path.stat()
        source_id = f"pbf:{path.name}:{st.st_size}:{int(st.st_mtime)}"
        fetch = lambda: fetch_pbf(path, bbox, True, log)  # noqa: E731  (always keep buildings)
        buildings = True
    elif d["source"] == "overpass":
        source_id = "overpass"
        fetch = lambda: fetch_overpass(d["overpass_urls"], bbox, buildings, log)  # noqa: E731
    else:
        raise ValueError(f"Unknown data.source {d['source']!r}")

    source_id = f"v{SCHEMA}:{source_id}"
    feats = cache.find(source_id, bbox, buildings)
    if feats is not None:
        log(f"  using cached data ({len(feats):,} features)")
        return feats
    t = time.time()
    feats = fetch()
    log(f"  fetched {len(feats):,} features in {time.time() - t:.1f}s")
    cache.store(source_id, bbox, buildings, feats)
    return feats
