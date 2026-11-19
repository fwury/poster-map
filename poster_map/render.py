"""Vector PDF rendering with ReportLab."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .geo import length_pt

CAPS = {"butt": 0, "round": 1, "square": 2}


class Painter:
    def __init__(self, c: canvas.Canvas, cx: float, cy: float, scale: float):
        self.c, self.cx, self.cy, self.s = c, cx, cy, scale

    def _pt(self, x, y):
        return self.cx + x * self.s, self.cy + y * self.s

    def _ring(self, path, coords):
        it = iter(coords)
        x, y = self._pt(*next(it))
        path.moveTo(x, y)
        for xy in it:
            path.lineTo(*self._pt(*xy))
        path.close()

    def fill(self, geom, color):
        if geom is None or geom.is_empty:
            return
        c = self.c
        path = c.beginPath()
        for poly in _polys(geom):
            self._ring(path, poly.exterior.coords)
            for r in poly.interiors:
                self._ring(path, r.coords)
        c.setFillColor(HexColor(color))
        c.drawPath(path, stroke=0, fill=1, fillMode=0)  # 0 = even-odd → holes work

    def stroke(self, geom, color, width, cap=1):
        if geom is None or geom.is_empty or width <= 0:
            return
        c = self.c
        path = c.beginPath()
        for line in _lines(geom):
            coords = line.coords
            if len(coords) < 2:
                continue
            it = iter(coords)
            path.moveTo(*self._pt(*next(it)))
            for xy in it:
                path.lineTo(*self._pt(*xy))
        c.setStrokeColor(HexColor(color))
        c.setLineWidth(width)
        c.setLineCap(cap)
        c.setLineJoin(1)
        c.drawPath(path, stroke=1, fill=0)


def _polys(g):
    if g.geom_type == "Polygon":
        yield g
    elif hasattr(g, "geoms"):
        for x in g.geoms:
            yield from _polys(x)


def _lines(g):
    if g.geom_type == "LineString":
        yield g
    elif g.geom_type == "LinearRing":
        yield g
    elif hasattr(g, "geoms"):
        for x in g.geoms:
            yield from _lines(x)


def _font(name: str) -> str:
    if name.lower().endswith((".ttf", ".otf")):
        fname = Path(name).stem
        if fname not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(fname, name))
        return fname
    return name


def _spaced(c, text, x_center, y, font, size, spacing, color):
    if not text:
        return
    w = pdfmetrics.stringWidth(text, font, size) + spacing * (len(text) - 1)
    t = c.beginText(x_center - w / 2, y)
    t.setFont(font, size)
    t.setCharSpace(spacing)
    t.setFillColor(HexColor(color))
    t.textLine(text)
    c.drawText(t)


def page_layout(cfg, page_w, page_h):
    pg = cfg["page"]
    m = length_pt(pg["margin"])
    mb = pg.get("margin_bottom")
    if mb is None:
        mb = m + (2.4 * 72 if cfg["text"]["enabled"] else 0)
    else:
        mb = length_pt(mb)
    return m, mb, page_w - 2 * m, page_h - m - mb  # x0, y0, w, h


def render_pdf(out_path, cfg, theme, layers, page_w, page_h, frame, center_ll):
    x0, y0, fw, fh, scale = frame
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(page_w, page_h))
    c.setTitle(cfg["text"].get("title") or "Map poster")
    c.setCreator("poster-map — map data © OpenStreetMap contributors (ODbL)")

    # Paper
    c.setFillColor(HexColor(theme["page"]))
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    cx, cy = x0 + fw / 2, y0 + fh / 2
    circle = cfg["area"].get("shape") == "circle"
    radius = min(fw, fh) / 2

    def clip_shape():
        p = c.beginPath()
        if circle:
            p.circle(cx, cy, radius)
        else:
            p.rect(x0, y0, fw, fh)
        return p

    c.saveState()
    c.clipPath(clip_shape(), stroke=0, fill=0)
    c.setFillColor(HexColor(theme["background"]))
    c.rect(x0, y0, fw, fh, stroke=0, fill=1)

    pt = Painter(c, cx, cy, scale)
    pt.fill(layers.get("green"), theme["green"])
    pt.fill(layers.get("water"), theme["water"])
    pt.fill(layers.get("buildings"), theme["buildings"])
    for kind, geom in (layers.get("waterways") or {}).items():
        pt.stroke(geom, theme["waterway"], cfg["waterways"]["widths"][kind])
    rs = float(cfg["roads"].get("scale", 1.0))
    pt.stroke(layers.get("rail"), theme["rail"], cfg["rail"]["width"] * rs, cap=0)
    cap = CAPS.get(cfg["roads"].get("cap", "round"), 1)
    for name, tier in cfg["roads"]["tiers"].items():
        geom = (layers.get("roads") or {}).get(name)
        if geom is None:
            continue
        color = tier.get("color") or theme["roads"].get(name, theme["road_default"])
        if tier.get("casing_width"):
            pt.stroke(geom, tier.get("casing_color", theme["background"]),
                      (tier["width"] + 2 * tier["casing_width"]) * rs, cap)
        pt.stroke(geom, color, tier["width"] * rs, cap)
    c.restoreState()

    # Frame line
    fwid = float(cfg["page"].get("frame_width") or 0)
    if fwid > 0:
        off = float(cfg["page"].get("frame_offset") or 0)
        c.setStrokeColor(HexColor(theme["frame"]))
        c.setLineWidth(fwid)
        if circle:
            c.circle(cx, cy, radius + off, stroke=1, fill=0)
        else:
            c.rect(x0 - off, y0 - off, fw + 2 * off, fh + 2 * off, stroke=1, fill=0)

    # Optional text block
    tx = cfg["text"]
    if tx.get("enabled"):
        font = _font(tx.get("font", "Helvetica"))
        base = y0 - 0.9 * 72 if not circle else cy - radius - 0.9 * 72
        _spaced(c, (tx.get("title") or "").upper(), page_w / 2, base, font,
                tx["title_size"], tx["letter_spacing"], theme["text"])
        line2 = tx.get("subtitle") or ""
        if tx.get("coords"):
            lat, lon = center_ll
            coord = (f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}  ·  "
                     f"{abs(lon):.4f}° {'E' if lon >= 0 else 'W'}")
            line2 = f"{line2}   ·   {coord}" if line2 else coord
        _spaced(c, line2.upper(), page_w / 2, base - tx["subtitle_size"] * 2.2, font,
                tx["subtitle_size"], tx["letter_spacing"] / 2, theme["text"])

    c.showPage()
    c.save()
