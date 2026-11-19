"""Built-in colour themes.

Keys:
  background  land / paper colour inside the map frame
  page        paper colour outside the map frame (margins)
  water, green, buildings, waterway, rail, frame, text
  roads       {tier_name: colour}; tiers not listed fall back to `road_default`
"""
from __future__ import annotations

import copy

THEMES: dict[str, dict] = {
    # Deep navy with warm gold streets.
    "midnight": {
        "background": "#13213a", "page": "#13213a",
        "water": "#0b1424", "green": "#172a42", "buildings": "#1a2b45",
        "waterway": "#0b1424", "rail": "#43506a", "frame": "#e8c170", "text": "#e8c170",
        "road_default": "#b8954f",
        "roads": {"motorway": "#f2cf7e", "primary": "#ecc56d", "secondary": "#e2b862",
                  "tertiary": "#d4aa5a", "residential": "#b8954f", "service": "#8a7449",
                  "path": "#6a5c43"},
    },
    # Warm cream paper with ink-black streets.
    "paper": {
        "background": "#f4ede1", "page": "#f4ede1",
        "water": "#c7d3d4", "green": "#e2e3cf", "buildings": "#e7ddcd",
        "waterway": "#c7d3d4", "rail": "#9a9488", "frame": "#1f1f1f", "text": "#1f1f1f",
        "road_default": "#2b2b2b",
        "roads": {"motorway": "#141414", "primary": "#1a1a1a", "secondary": "#202020",
                  "tertiary": "#262626", "residential": "#333333", "service": "#5e5e5e",
                  "path": "#8c8c8c"},
    },
    # Black and white.
    "noir": {
        "background": "#0e0e0e", "page": "#0e0e0e",
        "water": "#262626", "green": "#151515", "buildings": "#1a1a1a",
        "waterway": "#262626", "rail": "#4a4a4a", "frame": "#f2f2f2", "text": "#f2f2f2",
        "road_default": "#bdbdbd",
        "roads": {"motorway": "#ffffff", "primary": "#f5f5f5", "secondary": "#e6e6e6",
                  "tertiary": "#d6d6d6", "residential": "#bdbdbd", "service": "#7a7a7a",
                  "path": "#555555"},
    },
    # Soft blush pink with deep wine streets.
    "blush": {
        "background": "#f6e4dc", "page": "#f6e4dc",
        "water": "#e2b4a8", "green": "#efd4c8", "buildings": "#f0d8ce",
        "waterway": "#e2b4a8", "rail": "#c08f86", "frame": "#7c2434", "text": "#7c2434",
        "road_default": "#8e3a47",
        "roads": {"motorway": "#6e1c2c", "primary": "#74202f", "secondary": "#7c2434",
                  "tertiary": "#843040", "residential": "#8e3a47", "service": "#b07077",
                  "path": "#c99a9b"},
    },
    # Architectural blueprint.
    "blueprint": {
        "background": "#1d3b63", "page": "#1d3b63",
        "water": "#152d4e", "green": "#20426c", "buildings": "#22446e",
        "waterway": "#152d4e", "rail": "#5c7aa3", "frame": "#e9f1fb", "text": "#e9f1fb",
        "road_default": "#c9d9ee",
        "roads": {"motorway": "#ffffff", "primary": "#f2f7fd", "secondary": "#e6eef9",
                  "tertiary": "#d9e5f4", "residential": "#c2d4ea", "service": "#8aa6c9",
                  "path": "#6a88b0"},
    },
    # Sand background, slate water, rust streets.
    "terracotta": {
        "background": "#ece0cf", "page": "#ece0cf",
        "water": "#3e5a6b", "green": "#dcd2b8", "buildings": "#e3d5c1",
        "waterway": "#3e5a6b", "rail": "#a99b86", "frame": "#3e5a6b", "text": "#3e5a6b",
        "road_default": "#bf6a45",
        "roads": {"motorway": "#9e3d1f", "primary": "#a94526", "secondary": "#b14f2e",
                  "tertiary": "#b85a37", "residential": "#c26e4c", "service": "#d39a7d",
                  "path": "#dcb39b"},
    },
    # Muted sage green with forest-ink streets.
    "sage": {
        "background": "#e3e8dc", "page": "#e3e8dc",
        "water": "#9fb8b2", "green": "#d2dbc6", "buildings": "#dbe1d2",
        "waterway": "#9fb8b2", "rail": "#97a395", "frame": "#2c3b32", "text": "#2c3b32",
        "road_default": "#3c4c42",
        "roads": {"motorway": "#1f2b24", "primary": "#243129", "secondary": "#29372e",
                  "tertiary": "#304037", "residential": "#3c4c42", "service": "#6f7d72",
                  "path": "#949f95"},
    },
    # Dark charcoal with electric pink majors and cyan minors.
    "neon": {
        "background": "#0c0b16", "page": "#0c0b16",
        "water": "#141433", "green": "#11111f", "buildings": "#14132a",
        "waterway": "#141433", "rail": "#3a3360", "frame": "#ff4fa3", "text": "#ff4fa3",
        "road_default": "#3fc7d6",
        "roads": {"motorway": "#ff4fa3", "primary": "#ff6bb3", "secondary": "#f48ac4",
                  "tertiary": "#7fd8e3", "residential": "#3fb8c9", "service": "#2a7f8f",
                  "path": "#1f5a66"},
    },
    # Pale grey-white with steel-blue water and charcoal streets — gallery minimal.
    "gallery": {
        "background": "#f7f7f5", "page": "#f7f7f5",
        "water": "#d6e1e8", "green": "#eef0ea", "buildings": "#ececea",
        "waterway": "#d6e1e8", "rail": "#b9b9b9", "frame": "#2d2d2d", "text": "#2d2d2d",
        "road_default": "#4a4a4a",
        "roads": {"motorway": "#1e1e1e", "primary": "#262626", "secondary": "#2e2e2e",
                  "tertiary": "#383838", "residential": "#4a4a4a", "service": "#8a8a8a",
                  "path": "#b0b0b0"},
    },
    # ---- Room-matched: beige + forest green ---------------------------------
    # Warm beige paper, forest-green streets, soft sage water.
    "fern": {
        "background": "#ebe3d2", "page": "#ebe3d2",
        "water": "#b9c4b0", "green": "#dcdbc2", "buildings": "#e3dac8",
        "waterway": "#b9c4b0", "rail": "#a3a893", "frame": "#24402c", "text": "#24402c",
        "road_default": "#3f6147",
        "roads": {"motorway": "#1d3324", "primary": "#22402b", "secondary": "#294a32",
                  "tertiary": "#32553b", "residential": "#3f6147", "service": "#7d917f",
                  "path": "#a7b3a2"},
    },
    # Inverse: deep forest-green ground with cream/beige streets.
    "evergreen": {
        "background": "#1f3428", "page": "#1f3428",
        "water": "#15251c", "green": "#24392d", "buildings": "#243a2e",
        "waterway": "#15251c", "rail": "#4d6152", "frame": "#efe5cf", "text": "#efe5cf",
        "road_default": "#cfc6ac",
        "roads": {"motorway": "#f6eedb", "primary": "#f1e8d2", "secondary": "#eae0c7",
                  "tertiary": "#e0d6bb", "residential": "#c9c0a5", "service": "#8f9480",
                  "path": "#68766a"},
    },
    # Pale linen; two-tone streets: forest-green arteries over oat-beige side streets.
    "linen": {
        "background": "#f3eee3", "page": "#f3eee3",
        "water": "#ccd5c5", "green": "#e4e5d2", "buildings": "#ebe5d8",
        "waterway": "#ccd5c5", "rail": "#bdb7a6", "frame": "#2b4634", "text": "#2b4634",
        "road_default": "#b8ab90",
        "roads": {"motorway": "#1f3a29", "primary": "#264431", "secondary": "#2f4f3a",
                  "tertiary": "#5e7560", "residential": "#b5a88c", "service": "#cdc3ad",
                  "path": "#ddd5c4"},
    },
    # Sand-beige land, a solid deep pine-green lake, dark green-grey streets.
    "pine": {
        "background": "#e8dfcc", "page": "#e8dfcc",
        "water": "#2e4a3a", "green": "#d4d2b6", "buildings": "#ded5c1",
        "waterway": "#2e4a3a", "rail": "#a39f8a", "frame": "#2e4a3a", "text": "#2e4a3a",
        "road_default": "#3e4d43",
        "roads": {"motorway": "#1e2a23", "primary": "#233029", "secondary": "#29372f",
                  "tertiary": "#313f37", "residential": "#3e4d43", "service": "#7d867c",
                  "path": "#a6aa9c"},
    },
}


def resolve_theme(spec) -> dict:
    """`spec` is a theme name or a dict with optional `base` plus overrides."""
    if isinstance(spec, str):
        spec = {"base": spec}
    spec = dict(spec or {})
    base_name = spec.pop("base", "midnight")
    if base_name not in THEMES:
        raise ValueError(f"Unknown theme {base_name!r}. Available: {', '.join(THEMES)}")
    theme = copy.deepcopy(THEMES[base_name])
    roads = spec.pop("roads", None)
    theme.update(spec)
    if roads:
        theme["roads"] = {**theme["roads"], **roads}
    return theme
