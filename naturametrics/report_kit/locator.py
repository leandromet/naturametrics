"""The locator map: Brazil's states with the object marked — no network.

A ``LocatorMap`` block becomes an ordinary, vector-only ``MapComposition``
here, so both renderers draw it with the same code as any other map. The
state boundaries are the IBGE-derived simplified file Camposcope already
ships (``data/br_uf.simplified.geojson``, 99 KB).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import maps, style
from .model import LocatorMap, MapComposition, VectorLayer

_UF_PATH = Path(__file__).resolve().parent / "data" / "br_uf.simplified.geojson"

UF_FILL = "#e3e6ea"
UF_STROKE = "#ffffff"
UF_HIGHLIGHT = "#c9d8cf"


@lru_cache(maxsize=1)
def uf_collection() -> dict:
    return json.loads(_UF_PATH.read_text(encoding="utf-8"))


def _point_in_ring(lon: float, lat: float, ring: Sequence[Tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-300) + xi:
            inside = not inside
        j = i
    return inside


def uf_at(lon: float, lat: float) -> Optional[str]:
    """The UF containing (lon, lat), or None outside Brazil."""
    for feat in uf_collection()["features"]:
        for kind, rings in maps.iter_rings(feat):
            if kind == "polygon" and rings and _point_in_ring(lon, lat, rings[0]) and not any(
                    _point_in_ring(lon, lat, hole) for hole in rings[1:]):
                return feat["properties"].get("uf")
    return None


def _centre(geometry: dict) -> Tuple[float, float]:
    w, s, e, n = maps.bbox_of([geometry])
    return (w + e) / 2, (s + n) / 2


def compose(block: LocatorMap, accent: str = "#2f7d4f") -> MapComposition:
    """Vector-only composition for ``block``: every state, the object's
    state(s) highlighted, and the object as a point — or as its bounding box
    when that box is larger than about 2 % of the map width."""
    ufs = uf_collection()
    view = maps.MapView.from_geojson([ufs], slot=block.slot,
                                     aspect=style.LOCATOR_ASPECT, margin=0.03)
    highlight = set(block.highlight_ufs)
    lon, lat = _centre(block.geometry)
    if not highlight:
        found = uf_at(lon, lat)
        if found:
            highlight = {found}
    vectors: List[VectorLayer] = [
        VectorLayer(geojson=ufs, stroke=UF_STROKE, width_pt=0.4, fill=UF_FILL),
    ]
    if highlight:
        hi = {"type": "FeatureCollection", "features": [
            f for f in ufs["features"] if f["properties"].get("uf") in highlight]}
        vectors.append(VectorLayer(geojson=hi, stroke=UF_STROKE, width_pt=0.4,
                                   fill=UF_HIGHLIGHT))
    w, s, e, n = maps.bbox_of([block.geometry])
    fx0, _ = view.to_frac(w, s)
    fx1, _ = view.to_frac(e, n)
    if abs(fx1 - fx0) > 0.02:
        box = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
        vectors.append(VectorLayer(geojson=box, stroke=accent, width_pt=1.2))
    else:
        vectors.append(VectorLayer(geojson={"type": "Point", "coordinates": [lon, lat]},
                                   stroke="#ffffff", fill=accent, width_pt=0.8,
                                   point_radius_pt=3.2))
    # The label is the figure caption; a legend entry would only repeat it.
    return MapComposition(view=view, vectors=vectors,
                          attribution="IBGE — malha de UFs (simplificada)")
