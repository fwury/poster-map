# poster-map

Label-free, print-ready **vector PDF map posters** from OpenStreetMap data.
You give it an area, a paper size and a colour theme, and it draws streets,
water, parks, rivers and rail with no text on the map.

```bash
pip install -r requirements.txt
python -m poster_map configs/toronto.yaml --preview          # → output/toronto.pdf + .png
python -m poster_map configs/toronto.yaml --set theme=paper -o output/toronto-paper.pdf
python -m poster_map --themes                                # list built-in themes
```

## Data sources
| `data.source` | What | Notes |
|---|---|---|
| `overpass` (default) | Live query of the Overpass API for exactly your area | Works anywhere; tries several mirrors |
| `pbf` | A local or downloaded `.osm.pbf` extract (`data.pbf: path-or-URL`) | Fast and reliable offline; get city extracts from BBBike or Geofabrik |

Downloaded data is cached in `cache/`. Any later render whose area fits
inside a cached area reuses it, so style tweaks take a few seconds.

Lakes and seas are filled from OSM coastlines (land is on the left of the way).
Large water relations that are only partly in the data, like Lake Ontario in a
city extract, are rebuilt from the shoreline pieces that are present.

## Tweaking
Every option is in `poster_map/config.py` (`DEFAULTS`, with comments). Set
options in a YAML file or with `--set dotted.key=value`:

| Knob | Example |
|---|---|
| Area | `area.center=[43.66,-79.39]`, `area.place="Paris"`, `area.width_m=6000`, `area.bbox=[s,w,n,e]` |
| Shape / rotation | `area.shape=circle`, `area.rotation_deg=16.7` |
| Paper | `page.size=24x36in` (or `A2`, `50x70cm`), `page.orientation=landscape`, `page.margin=0` (full bleed) |
| Frame line | `page.frame_width=2 page.frame_offset=8` |
| Theme | `theme=terracotta`, or a dict: `theme: {base: noir, water: "#223344", roads: {motorway: "#ff0000"}}` |
| Road weights | `roads.scale=1.3`, `roads.tiers.residential.width=0.7`, `roads.tiers.path.enabled=true` |
| Road colour per tier | `roads.tiers.primary.color="#ffcc00"`; outline with `casing_width` / `casing_color` |
| Layers | `layers.buildings=true`, `layers.green=false`, `layers.rail=false`, `layers.water=false` |
| Optional text | `text.enabled=true text.title=Toronto` (off by default) |

Built-in themes: midnight, paper, noir, blush, blueprint, terracotta, sage, neon, gallery, and four beige / forest-green room themes: fern, evergreen, linen, pine.

Line widths are in points on paper (1 pt = 1/72 in), so they print at the same
thickness whatever the map scale.

Map data © OpenStreetMap contributors, available under the ODbL.
