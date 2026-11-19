"""Command-line entry point:  python -m poster_map CONFIG.yaml [--set key=value ...]"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import load_config
from .data import get_features
from .geo import Projection, geocode, page_size_pt
from .layers import LayerBuilder, frame_rotation_extent
from .render import page_layout, render_pdf
from .themes import THEMES, resolve_theme


def build(cfg: dict, log=print) -> Path:
    t0 = time.time()
    page_w, page_h = page_size_pt(cfg["page"]["size"], cfg["page"].get("orientation", "portrait"))
    x0, y0, fw, fh = page_layout(cfg, page_w, page_h)

    # --- area → centre + ground extent matching the frame's aspect ratio ----
    a = cfg["area"]
    if a.get("bbox"):
        s, w, n, e = a["bbox"]
        lat0, lon0 = (s + n) / 2, (w + e) / 2
        proj = Projection(lat0, lon0)
        gw = proj.fwd(e, lat0)[0] - proj.fwd(w, lat0)[0]
        gh = proj.fwd(lon0, n)[1] - proj.fwd(lon0, s)[1]
        fit = a.get("fit", "contain")
        # contain: the whole bbox is visible (extra area shows on the long side)
        # cover:   the frame is filled with the bbox (one axis gets cropped)
        scale = max(fw / gw, fh / gh) if fit == "cover" else min(fw / gw, fh / gh)
    else:
        if a.get("center"):
            lat0, lon0 = map(float, a["center"])
        elif a.get("place"):
            log(f"Geocoding {a['place']!r} …")
            lat0, lon0 = geocode(a["place"])
        else:
            raise ValueError("Set area.center, area.place or area.bbox")
        proj = Projection(lat0, lon0)
        scale = fw / float(a["width_m"])
    half_w, half_h = fw / 2 / scale, fh / 2 / scale
    log(f"Map: centre {lat0:.5f}, {lon0:.5f}; {2 * half_w / 1000:.2f} × {2 * half_h / 1000:.2f} km "
        f"on {page_w / 72:.1f} × {page_h / 72:.1f} in (1:{1 / scale * 72 / 0.0254:,.0f})")

    # --- data --------------------------------------------------------------
    ew, eh = frame_rotation_extent(half_w, half_h, float(a.get("rotation_deg") or 0))
    pad = 1 + float(cfg["data"].get("padding", 0.05))
    w_, s_ = proj.inv(-ew * pad, -eh * pad)
    e_, n_ = proj.inv(ew * pad, eh * pad)
    bbox = tuple(round(v, 5) for v in (s_, w_, n_, e_))
    want_buildings = cfg["data"].get("include_buildings")
    if want_buildings is None:
        want_buildings = bool(cfg["layers"].get("buildings"))
    log(f"Loading OSM data for bbox {bbox} from {cfg['data']['source']} …")
    feats = get_features(cfg, bbox, want_buildings, log)

    # --- geometry + render ---------------------------------------------------
    log("Building layers …")
    layers = LayerBuilder(cfg, proj, half_w, half_h, scale, log).build(feats)
    theme = resolve_theme(cfg["theme"])
    out = Path(cfg["output"])
    log(f"Rendering {out} …")
    render_pdf(out, cfg, theme, layers, page_w, page_h, (x0, y0, fw, fh, scale), (lat0, lon0))
    log(f"Done in {time.time() - t0:.1f}s → {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def preview(pdf: Path, png: Path, dpi: int) -> Path:
    import fitz  # pymupdf

    png.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    doc[0].get_pixmap(dpi=dpi).save(png)
    return png


def main(argv=None):
    ap = argparse.ArgumentParser(prog="poster_map", description=__doc__)
    ap.add_argument("config", nargs="?", help="YAML config file")
    ap.add_argument("--set", "-s", action="append", default=[], metavar="KEY=VALUE",
                    help="override a config value, e.g. --set theme=paper "
                         "--set area.width_m=6000 --set roads.tiers.path.enabled=true")
    ap.add_argument("--output", "-o", help="output PDF path")
    ap.add_argument("--preview", type=int, metavar="DPI", nargs="?", const=40,
                    help="also write a PNG preview next to the PDF (default 40 dpi)")
    ap.add_argument("--themes", action="store_true", help="list built-in themes and exit")
    args = ap.parse_args(argv)

    if args.themes:
        print("\n".join(THEMES))
        return 0
    cfg = load_config(args.config, args.set)
    if args.output:
        cfg["output"] = args.output
    out = build(cfg)
    if args.preview:
        png = preview(out, out.with_suffix(".png"), args.preview)
        print(f"Preview → {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
