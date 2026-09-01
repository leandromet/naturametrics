"""IBAMA embargos as a live, browser-fetched vector layer.

Unlike every other layer in this app, this one is not Earth Engine and not a
locally-held table: it is IBAMA's own ArcGIS MapServer
(config.datasets.IBAMA_EMBARGOS), queried per-viewport, live, on every pan.
The dynamic-vector-layer pipeline it plugs into — ``"dynamic": True`` +
``west/south/east/north`` query params, refetched on every map "settle" — is
the same one services/ifn.py's interactive conglomerado layer already
established; components/map/leaflet_map.js needs no changes to serve this.

**This function must never raise.** ``ifn.points_in_bbox`` gets to be a bare,
unguarded local-memory scan because it structurally cannot fail; this one does
real network I/O against a third party, on their own refresh schedule and out
of our control, and it is called silently on every map movement with nowhere
to show a raised exception. Any failure is caught here and reported in the
returned FeatureCollection's own ``properties.error`` instead — the same
convention ``ifn.points_in_bbox`` uses for ``truncated``.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from ..config import datasets as ds
from ..config.settings import (
    EMBARGOS_CACHE_TTL_S,
    EMBARGOS_MAX_PAGES,
    EMBARGOS_MIN_ZOOM,
    EMBARGOS_PAGE_SIZE,
    EMBARGOS_TIMEOUT_CONNECT,
    EMBARGOS_TIMEOUT_READ,
)

logger = logging.getLogger(__name__)

_CONF = ds.IBAMA_EMBARGOS
_F = _CONF["fields"]
_TIMEOUT = (EMBARGOS_TIMEOUT_CONNECT, EMBARGOS_TIMEOUT_READ)

#: Date fields the ArcGIS service returns as epoch-millisecond integers —
#: unreadable in a tooltip unmodified, so they are rewritten to plain
#: ISO dates before the response leaves this module.
_DATE_FIELDS = (_F["tad_date"], _F["registered"])

#: Path served by the backend (see naturametrics/api). Relative, like
#: biomes.GEOJSON_PATH / ifn.GEOJSON_PATH — the map component resolves it
#: against the backend origin.
GEOJSON_PATH = "/_embargos.geojson"

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update({
                    "User-Agent": "naturametrics/1.0 (contact: leandromet@gmail.com)",
                    "Accept": "application/json",
                })
                _session = s
    return _session


# --------------------------------------------------------------------------- #
# Short-lived cache — de-duplicates the debounced refetch bursts a pan/zoom
# produces (leaflet_map.js's "settle" handler), not a long-term store.
# --------------------------------------------------------------------------- #
@dataclass
class _Entry:
    value: Any
    stored_at: float

    def fresh(self) -> bool:
        return (time.time() - self.stored_at) < EMBARGOS_CACHE_TTL_S


_cache: dict[str, _Entry] = {}
_cache_lock = threading.Lock()


def _bbox_key(west: float, south: float, east: float, north: float) -> str:
    # Rounded to 3dp (~100 m), matching the client's own rounding in
    # leaflet_map.js's specUrl — a finer key would never hit the cache at all.
    return f"embargos:{west:.3f}:{south:.3f}:{east:.3f}:{north:.3f}"


def _normalize_dates(features: list[dict]) -> None:
    """ArcGIS ships date fields as epoch-millisecond ints. In place."""
    import datetime

    for feature in features:
        props = feature.get("properties") or {}
        for field in _DATE_FIELDS:
            value = props.get(field)
            if isinstance(value, (int, float)) and value > 0:
                try:
                    props[field] = datetime.datetime.utcfromtimestamp(
                        value / 1000
                    ).strftime("%Y-%m-%d")
                except (OverflowError, OSError, ValueError):
                    pass


def _fetch_page(west: float, south: float, east: float, north: float,
                offset: int) -> dict:
    params = {
        "geometry": f"{west},{south},{east},{north}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(_F.values()),
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": EMBARGOS_PAGE_SIZE,
        "resultOffset": offset,
    }
    session = get_session()
    last: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            r = session.get(_CONF["query_url"], params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            last = exc
            logger.warning("IBAMA embargos request failed (attempt %d): %s",
                           attempt, exc)
            continue
        if r.status_code != 200:
            last = RuntimeError(f"HTTP {r.status_code}")
            continue
        try:
            return r.json()
        except ValueError as exc:
            last = exc
            continue
    raise RuntimeError(f"IBAMA embargos service unreachable: {last}")


def _fetch(west: float, south: float, east: float, north: float) -> dict:
    features: list[dict] = []
    for page in range(EMBARGOS_MAX_PAGES):
        payload = _fetch_page(west, south, east, north, page * EMBARGOS_PAGE_SIZE)
        page_features = payload.get("features", [])
        features.extend(page_features)
        if len(page_features) < EMBARGOS_PAGE_SIZE:
            break  # last page

    _normalize_dates(features)
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "truncated": len(features) >= EMBARGOS_PAGE_SIZE * EMBARGOS_MAX_PAGES,
        },
    }


def polygons_in_bbox(west: float, south: float, east: float, north: float) -> dict:
    """Embargo polygons intersecting a viewport, as GeoJSON. Never raises."""
    key = _bbox_key(west, south, east, north)
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and hit.fresh():
            return hit.value

    try:
        value = _fetch(west, south, east, north)
    except Exception as exc:  # noqa: BLE001
        logger.warning("IBAMA embargos query failed for %s: %s", key, exc)
        value = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"error": str(exc)},
        }

    with _cache_lock:
        _cache[key] = _Entry(value, time.time())
    return value


def vector_spec(opacity: float = 0.7, min_zoom: int | None = None,
                z_index: int = 25) -> dict:
    """Spec for the dynamic, browser-fetched embargos layer.

    Purely declarative, like ifn.vector_spec — the fetch itself happens in
    the browser via components/map/leaflet_map.js's generic dynamic-layer
    pipeline, which needs no per-layer code of its own.
    """
    return {
        "id": "embargos_ibama",
        "path": GEOJSON_PATH,
        "dynamic": True,
        "min_zoom": EMBARGOS_MIN_ZOOM if min_zoom is None else min_zoom,
        "z_index": z_index,
        "opacity": opacity,
        "attribution": _CONF["attribution"],
        "default_color": _CONF["default_color"],
        "weight": 1.5,
        # No point_style: this is a polygon layer, styled generically by
        # leaflet_map.js's styleFor() falling back to default_color since no
        # color_property/palette is set here — nothing to categorise by.
        "tooltip": [
            {"label": "Autuado", "property": _F["person"]},
            {"label": "TAD", "property": _F["tad_number"]},
            {"label": "Data do TAD", "property": _F["tad_date"]},
            {"label": "Município", "property": _F["municipality"]},
            {"label": "UF", "property": _F["uf"]},
            {"label": "Desmatamento", "property": _F["situation"]},
            {"label": "Infração", "property": _F["infraction"]},
            {"label": "Área declarada", "property": _F["area"]},
        ],
    }


__all__ = ["GEOJSON_PATH", "polygons_in_bbox", "vector_spec", "get_session"]
