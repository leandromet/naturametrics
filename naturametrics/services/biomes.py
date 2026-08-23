"""IBGE biomes: the polygons behind the map overlay and the IFN biome filter.

**Why this one layer is a vector and every other is a tile.** Everything else the
map draws is painted by Earth Engine and delivered as tiles (decision D1) — the
browser never sees a geometry. That is the right trade for raster data and for
17 495 points, but it cannot answer "what is under the cursor": a tile is pixels.
The biome layer has to name itself on hover, so the browser needs the actual
polygons.

The full 1:250 000 asset is ~40 MB of coordinates, which is not shippable. What
is served instead is simplified to 1.5 km and rounded to two decimal places
(~1.1 km, matched to the simplification so the rounding never adds error the
simplification did not already allow) — about 2.5 MB of JSON, 0.5 MB over the
wire once gzipped.

That is a deliberate accuracy trade: **boundaries drawn from this layer are
approximate to roughly a kilometre and must not be used to decide which biome a
specific coordinate falls in.** Nothing does. The one place that question is
asked — which biome each IFN point sits in — was answered once, at full
resolution, by ``scripts/join_ifn_biomes.py``, and stored (see
:mod:`naturametrics.services.ifn`).

Built once, then cached on disk, because the source asset never changes.
"""

from __future__ import annotations

import gzip
import json
import logging
import threading
import time
from pathlib import Path

from ..config import datasets as ds
from ..config.settings import REPO_ROOT

logger = logging.getLogger(__name__)

#: Simplification tolerance in metres, and the matching coordinate precision.
SIMPLIFY_M = 1500
COORD_DECIMALS = 2

#: Properties carried to the browser. Everything else in the asset is dropped —
#: each extra string field costs ~15 KB across 271 features.
TOOLTIP_PROPERTIES = ("nm_bm", "nm_dm_fito", "nm_reg_nat", "vg_dom")

CACHE_PATH = REPO_ROOT / "data" / "cache" / "ibge_biomes_250k.json.gz"

_memo: bytes | None = None
_memo_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Simplified GeoJSON — what the browser draws
# --------------------------------------------------------------------------- #

def _clean_ring(ring: list, dp: int) -> list | None:
    """Round a ring and drop the duplicate vertices rounding creates.

    Without the dedup, rounding *adds* bytes: long stretches of coastline
    collapse onto the same rounded coordinate and each repeat still costs its
    characters. A ring needs 4 positions to close; anything shorter is a sliver
    the simplification has already destroyed.
    """
    out: list[list[float]] = []
    for x, y in ring:
        pos = [round(x, dp), round(y, dp)]
        if not out or out[-1] != pos:
            out.append(pos)
    if len(out) < 4:
        return None
    if out[0] != out[-1]:
        out.append(list(out[0]))
    return out


def _clean_geometry(geom: dict, dp: int) -> dict | None:
    """Reduce any geometry to a Polygon/MultiPolygon, or drop it.

    ``simplify`` turns the smallest islands into LineStrings and Points, and
    some features come back as GeometryCollections. Leaflet would render the
    degenerate ones as invisible zero-area shapes that still sit in the hit-test
    path and steal hovers from the polygon underneath, so they are removed here
    rather than filtered in the browser.
    """
    kind = geom.get("type")

    if kind == "Polygon":
        rings = [r for r in (_clean_ring(r, dp) for r in geom["coordinates"]) if r]
        return {"type": "Polygon", "coordinates": rings} if rings else None

    if kind == "MultiPolygon":
        polys = []
        for poly in geom["coordinates"]:
            rings = [r for r in (_clean_ring(r, dp) for r in poly) if r]
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None

    if kind == "GeometryCollection":
        parts = [g for g in (_clean_geometry(g, dp) for g in geom.get("geometries", [])) if g]
        if not parts:
            return None
        polys: list = []
        for part in parts:
            if part["type"] == "MultiPolygon":
                polys.extend(part["coordinates"])
            else:
                polys.append(part["coordinates"])
        return {"type": "MultiPolygon", "coordinates": polys}

    return None  # Point, LineString — degenerate remains of simplification


def build_geojson() -> dict:
    """Fetch and simplify the biome polygons. Blocking, ~10 s against Earth Engine."""
    import ee

    from .ee_client import get_ee

    get_ee()
    conf = ds.IBGE_BIOME_DOMAIN
    started = time.time()

    collection = (
        ee.FeatureCollection(conf["asset"])
        .select(list(TOOLTIP_PROPERTIES))
        .map(lambda f: f.setGeometry(f.geometry().simplify(SIMPLIFY_M)))
    )
    raw = collection.getInfo()

    features = []
    for feature in raw.get("features", []):
        geom = _clean_geometry(feature.get("geometry") or {}, COORD_DECIMALS)
        if geom is None:
            continue
        features.append({
            "type": "Feature",
            "properties": feature.get("properties", {}),
            "geometry": geom,
        })

    logger.info(
        "Built biome GeoJSON: %s/%s features in %.1f s",
        len(features), len(raw.get("features", [])), time.time() - started,
    )
    return {"type": "FeatureCollection", "features": features}


def geojson_gzipped() -> bytes:
    """The simplified biome GeoJSON, gzip-compressed, memoised and disk-cached.

    Three tiers because each one removes a different cost: the memo removes the
    disk read, the disk cache removes the Earth Engine round trip, and the gzip
    is stored rather than recomputed because it is the same 0.5 MB every time.
    """
    global _memo

    with _memo_lock:
        if _memo is not None:
            return _memo

    if CACHE_PATH.exists():
        try:
            payload = CACHE_PATH.read_bytes()
            with _memo_lock:
                _memo = payload
            logger.info("Biome GeoJSON from disk cache (%s KiB)", len(payload) // 1024)
            return payload
        except OSError as exc:
            logger.warning("Biome cache unreadable (%s) — rebuilding", exc)

    body = json.dumps(build_geojson(), separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    payload = gzip.compress(body, 9)

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Written via a temporary file: two workers building this at once would
        # otherwise interleave into a corrupt gzip that then fails forever.
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_bytes(payload)
        tmp.replace(CACHE_PATH)
    except OSError as exc:
        logger.warning("Could not cache biome GeoJSON (%s) — serving from memory", exc)

    with _memo_lock:
        _memo = payload
    logger.info("Biome GeoJSON ready: %s KiB gzipped", len(payload) // 1024)
    return payload


# --------------------------------------------------------------------------- #
# Layer spec
# --------------------------------------------------------------------------- #

#: Path served by the backend (see :mod:`naturametrics.api`). Relative — the map
#: component resolves it against the backend origin, which differs between the
#: split dev ports and single-port production.
GEOJSON_PATH = "/_biomes.geojson"

#: 271 polygons' worth of labels is unreadable zoomed out to the whole of
#: Brazil — this is the zoom level (leaflet_map.js's applyLabelVisibility)
#: below which they are hidden regardless of the "show labels" toggle.
LABEL_MIN_ZOOM = 7


def vector_spec(opacity: float = 0.45, z_index: int = 5, show_labels: bool = True) -> dict:
    """Spec for the browser-side biome layer.

    Purely declarative and involves no Earth Engine call, so unlike every tile
    spec it cannot fail — the fetch happens in the browser.
    """
    conf = ds.IBGE_BIOME_DOMAIN
    return {
        # The labels suffix makes "show labels" part of the layer's identity:
        # toggling it must force leaflet_map.js's diff to treat this as a
        # DIFFERENT layer and rebuild from scratch, rather than patch the
        # existing one in place. Label markers are only ever created once, at
        # build time (see buildLayer) — a layer built before this flag
        # existed, or before a code change added new marker-building logic,
        # has no markers to patch, and a same-id "cheap property update"
        # would silently do nothing.
        "id": f"ibge_biomes:{'lbl' if show_labels else 'nolbl'}",
        "path": GEOJSON_PATH,
        "opacity": opacity,
        "z_index": z_index,
        "attribution": conf["attribution"],
        "color_property": conf["fields"]["biome"],
        "palette": conf["palette"],
        "default_color": "9e9e9e",
        "weight": conf["outline_width"],
        # A permanent on-map label per polygon (leaflet_map.js), separate
        # from the hover tooltip below — natural region is the more legible
        # unit to label at a glance than the biome/domain fill colour alone.
        # Omitted entirely (not just hidden) when the toggle is off — paired
        # with the id suffix above, that makes "show labels" a genuinely
        # different layer rather than a same-id in-place patch.
        "label_property": conf["fields"]["natural_region"] if show_labels else None,
        "label_min_zoom": LABEL_MIN_ZOOM,
        "tooltip": [
            {"label": "Bioma", "property": "nm_bm"},
            {"label": "Domínio fitogeográfico", "property": "nm_dm_fito"},
            {"label": "Região natural", "property": "nm_reg_nat"},
            {"label": "Vegetação dominante", "property": "vg_dom"},
        ],
    }
