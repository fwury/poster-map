"""Configuration: defaults, YAML loading, deep-merge and command-line overrides."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

# Every key here can be overridden from a YAML config file or with
# `--set dotted.key=value` on the command line.
DEFAULTS: dict = {
    "output": "output/poster.pdf",

    # ---- What area to draw -------------------------------------------------
    "area": {
        "place": None,          # free-text place name, geocoded with Nominatim
        "center": None,         # [lat, lon]; wins over `place`
        "width_m": 8000,        # horizontal ground extent of the map frame (metres)
        "bbox": None,           # [south, west, north, east]; overrides center/width.
                                # The frame is filled ("cover"), so one axis may be cropped.
        "shape": "rect",        # rect | circle
        "rotation_deg": 0,      # rotate the map clockwise (e.g. align with a street grid)
    },

    # ---- Where data comes from ---------------------------------------------
    "data": {
        "source": "overpass",   # overpass | pbf
        "pbf": None,            # path or URL of an .osm.pbf extract (source: pbf)
        "overpass_urls": [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        ],
        "cache_dir": "cache",
        "padding": 0.05,        # fetch a bit beyond the frame (fraction)
        "skip_tunnels": True,   # tunnels/underground lines aren't drawn
        "include_buildings": None,  # None = only if the buildings layer is on
    },

    # ---- Paper -------------------------------------------------------------
    "page": {
        "size": "18x24in",      # "18x24in", "24x36in", "A2", "50x70cm", or [w, h] in points
        "orientation": "portrait",  # portrait | landscape
        "margin": "0.75in",     # space around the map frame (0 = full bleed)
        "margin_bottom": None,  # extra room for a title block; None = same as margin
        "frame_width": 0,       # border line around the map, points (0 = none)
        "frame_offset": 0,      # gap between map and border line, points
    },

    # ---- Optional text block (off by default: label-free poster) ------------
    "text": {
        "enabled": False,
        "title": "",
        "subtitle": "",
        "coords": True,         # print the centre coordinates
        "font": "Helvetica",    # built-in PDF font name, or path to a .ttf
        "title_size": 48,
        "subtitle_size": 16,
        "letter_spacing": 6,
    },

    # ---- Which layers to draw ----------------------------------------------
    "layers": {
        "water": True,
        "green": True,
        "buildings": False,
        "waterways": True,
        "rail": True,
        "roads": True,
    },

    # ---- Road classes (drawn bottom→top in this order) ----------------------
    # width is in points on paper (1 pt = 1/72 in), independent of map scale.
    "roads": {
        "scale": 1.0,           # multiply every width (quick "bolder/lighter" knob)
        "cap": "round",
        "tiers": {
            "path":        {"enabled": False, "width": 0.20,
                            "highway": ["footway", "path", "cycleway", "steps", "track",
                                        "bridleway", "corridor"]},
            "service":     {"enabled": True, "width": 0.30,
                            "highway": ["service", "pedestrian", "living_street"]},
            "residential": {"enabled": True, "width": 0.55,
                            "highway": ["residential", "unclassified", "road"]},
            "tertiary":    {"enabled": True, "width": 0.90,
                            "highway": ["tertiary", "tertiary_link"]},
            "secondary":   {"enabled": True, "width": 1.25,
                            "highway": ["secondary", "secondary_link"]},
            "primary":     {"enabled": True, "width": 1.65,
                            "highway": ["primary", "primary_link"]},
            "motorway":    {"enabled": True, "width": 2.30,
                            "highway": ["motorway", "motorway_link", "trunk", "trunk_link"]},
        },
    },
    "rail": {"width": 0.5, "types": ["rail", "light_rail", "tram", "subway", "narrow_gauge"]},
    "waterways": {"widths": {"river": 1.6, "canal": 1.2, "stream": 0.5}},

    # ---- Colours -------------------------------------------------------------
    # Either a built-in theme name, or a mapping {base: <theme>, <key>: <colour>, ...}
    "theme": "midnight",
}


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def apply_set(cfg: dict, assignment: str) -> None:
    """Apply `a.b.c=value`; value is parsed as YAML (numbers, lists, bools...)."""
    if "=" not in assignment:
        raise ValueError(f"--set expects key=value, got {assignment!r}")
    key, raw = assignment.split("=", 1)
    value = yaml.safe_load(raw) if raw.strip() else None
    node = cfg
    parts = key.strip().split(".")
    for p in parts[:-1]:
        if not isinstance(node.get(p), dict):
            node[p] = {}
        node = node[p]
    node[parts[-1]] = value


def load_config(path: str | None, sets: list[str] | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        cfg = deep_merge(cfg, user)
        cfg["_config_dir"] = str(Path(path).resolve().parent)
    for s in sets or []:
        apply_set(cfg, s)
    return cfg
