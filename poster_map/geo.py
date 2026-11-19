"""Geocoding, page geometry and a local metric projection."""
from __future__ import annotations

import math
import re

import requests

EARTH_R = 6_371_008.8
UA = "poster-map/0.1 (open-source map poster generator)"

UNIT_PT = {"in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "pt": 1.0}
ISO = {  # mm, portrait
    "A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420), "A4": (210, 297),
    "B1": (707, 1000), "B2": (500, 707), "LETTER": (215.9, 279.4), "TABLOID": (279.4, 431.8),
}


def length_pt(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"\s*([\d.]+)\s*(in|cm|mm|pt)?\s*", str(v))
    if not m:
        raise ValueError(f"Can't parse length {v!r}")
    return float(m.group(1)) * UNIT_PT[m.group(2) or "pt"]


def page_size_pt(size, orientation="portrait") -> tuple[float, float]:
    if isinstance(size, (list, tuple)):
        w, h = float(size[0]), float(size[1])
    elif str(size).upper() in ISO:
        w, h = (x * UNIT_PT["mm"] for x in ISO[str(size).upper()])
    else:
        m = re.fullmatch(r"\s*([\d.]+)\s*x\s*([\d.]+)\s*(in|cm|mm|pt)\s*", str(size), re.I)
        if not m:
            raise ValueError(f"Can't parse page size {size!r} (try '18x24in', 'A2', '50x70cm')")
        u = UNIT_PT[m.group(3).lower()]
        w, h = float(m.group(1)) * u, float(m.group(2)) * u
    w, h = min(w, h), max(w, h)
    return (h, w) if orientation == "landscape" else (w, h)


def geocode(place: str) -> tuple[float, float]:
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": UA}, timeout=30,
    )
    r.raise_for_status()
    hits = r.json()
    if not hits:
        raise ValueError(f"Nominatim found nothing for {place!r}")
    return float(hits[0]["lat"]), float(hits[0]["lon"])


class Projection:
    """Local equirectangular projection in metres around (lat0, lon0).

    Accurate to well under 0.1% across a city-sized poster, and keeps
    north up / scale uniform without any heavy GIS dependency.
    """

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self.kx = math.radians(1) * EARTH_R * math.cos(math.radians(lat0))
        self.ky = math.radians(1) * EARTH_R

    def fwd(self, lon: float, lat: float) -> tuple[float, float]:
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def inv(self, x: float, y: float) -> tuple[float, float]:
        return (self.lon0 + x / self.kx, self.lat0 + y / self.ky)
