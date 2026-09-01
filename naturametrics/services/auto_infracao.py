"""IBAMA autos de infração (infraction notices) as a live vector layer.

A different, complementary dataset to services/embargos.py: an "auto de
infração" is the citation itself; an embargo is the follow-on restriction on
the land, and not every citation carries one. Same publisher, same
per-viewport dynamic-vector-layer mechanism (see embargos.py's own docstring
for the shape of that pipeline — components/map/leaflet_map.js needs no
per-layer code for either).

**Far denser than embargos**: 709 803 rows nationwide vs. 91 120 polygons
(both verified live 2026-08-31), and a modest bbox around a single city
already maxed a 2 000-row page — hence the higher
config.settings.AUTO_INFRACAO_MIN_ZOOM.

**Points, via REST — not WFS.** This service also exposes a WFS endpoint,
but its GeoJSON output is malformed for any record with no recorded
coordinate: a dangling ``"geometry":{"type":"Point",}`` with no
``coordinates`` key, which is not valid JSON at all. The plain ArcGIS REST
``/query`` endpoint used here does not have this problem — confirmed against
the same bbox — so WFS was dropped rather than worked around.

**This function must never raise**, same reasoning as
``embargos.polygons_in_bbox``: called silently on every map movement, with
nowhere to show a raised exception.
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
    AUTO_INFRACAO_CACHE_TTL_S,
    AUTO_INFRACAO_MAX_PAGES,
    AUTO_INFRACAO_MIN_ZOOM,
    AUTO_INFRACAO_PAGE_SIZE,
    AUTO_INFRACAO_TIMEOUT_CONNECT,
    AUTO_INFRACAO_TIMEOUT_READ,
)

logger = logging.getLogger(__name__)

_CONF = ds.IBAMA_AUTO_INFRACAO
_F = _CONF["fields"]
_TIMEOUT = (AUTO_INFRACAO_TIMEOUT_CONNECT, AUTO_INFRACAO_TIMEOUT_READ)

#: Date fields the ArcGIS service returns as epoch-millisecond integers —
#: unreadable in a tooltip unmodified, so they are rewritten to plain ISO
#: dates before the response leaves this module.
_DATE_FIELDS = (_F["date"],)

#: Path served by the backend (see naturametrics/api). Relative, like
#: embargos.GEOJSON_PATH — the map component resolves it against the backend
#: origin.
GEOJSON_PATH = "/_auto_infracao.geojson"

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
        return (time.time() - self.stored_at) < AUTO_INFRACAO_CACHE_TTL_S


_cache: dict[str, _Entry] = {}
_cache_lock = threading.Lock()


def _bbox_key(west: float, south: float, east: float, north: float) -> str:
    # Rounded to 3dp (~100 m), matching the client's own rounding in
    # leaflet_map.js's specUrl — a finer key would never hit the cache at all.
    return f"auto_infracao:{west:.3f}:{south:.3f}:{east:.3f}:{north:.3f}"


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
        "resultRecordCount": AUTO_INFRACAO_PAGE_SIZE,
        "resultOffset": offset,
    }
    session = get_session()
    last: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            r = session.get(_CONF["query_url"], params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            last = exc
            logger.warning("IBAMA auto de infração request failed (attempt %d): %s",
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
    raise RuntimeError(f"IBAMA auto de infração service unreachable: {last}")


def _fetch(west: float, south: float, east: float, north: float) -> dict:
    features: list[dict] = []
    for page in range(AUTO_INFRACAO_MAX_PAGES):
        payload = _fetch_page(west, south, east, north,
                              page * AUTO_INFRACAO_PAGE_SIZE)
        page_features = payload.get("features", [])
        features.extend(page_features)
        if len(page_features) < AUTO_INFRACAO_PAGE_SIZE:
            break  # last page

    _normalize_dates(features)
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "truncated": len(features)
                        >= AUTO_INFRACAO_PAGE_SIZE * AUTO_INFRACAO_MAX_PAGES,
        },
    }


def points_in_bbox(west: float, south: float, east: float, north: float) -> dict:
    """Infraction points intersecting a viewport, as GeoJSON. Never raises."""
    key = _bbox_key(west, south, east, north)
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and hit.fresh():
            return hit.value

    try:
        value = _fetch(west, south, east, north)
    except Exception as exc:  # noqa: BLE001
        logger.warning("IBAMA auto de infração query failed for %s: %s", key, exc)
        value = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"error": str(exc)},
        }

    with _cache_lock:
        _cache[key] = _Entry(value, time.time())
    return value


def vector_spec(opacity: float = 0.85, min_zoom: int | None = None,
                z_index: int = 26) -> dict:
    """Spec for the dynamic, browser-fetched infraction-points layer.

    One z_index above embargos (25): a citation pin should sit visibly on
    top of the embargo polygon it may belong to, not underneath it.
    """
    return {
        "id": "auto_infracao_ibama",
        "path": GEOJSON_PATH,
        "dynamic": True,
        "min_zoom": AUTO_INFRACAO_MIN_ZOOM if min_zoom is None else min_zoom,
        "z_index": z_index,
        "opacity": opacity,
        "attribution": _CONF["attribution"],
        # Small circle markers — leaflet_map.js's pointToLayer branch fires
        # whenever point_style is set (see biomes.py's polygon-only spec for
        # the contrast: no point_style there at all).
        "point_style": {
            "radius": 4,
            "color": "#ffffff",
            "weight": 1,
            "fillColor": f"#{_CONF['default_color']}",
            "fillOpacity": opacity,
        },
        "hover_style": {
            "radius": 7,
            "color": "#ffffff",
            "weight": 1.5,
            "fillColor": f"#{_CONF['default_color']}",
            "fillOpacity": 1.0,
        },
        "tooltip": [
            {"label": "Autuado", "property": _F["infrator"]},
            {"label": "Auto de infração", "property": _F["auto_number"]},
            {"label": "Data", "property": _F["date"]},
            {"label": "Município", "property": _F["municipality"]},
            {"label": "UF", "property": _F["uf"]},
            {"label": "Infração", "property": _F["infraction"]},
            {"label": "Valor da multa (R$)", "property": _F["value"]},
            {"label": "Situação", "property": _F["status"]},
        ],
    }


__all__ = ["GEOJSON_PATH", "points_in_bbox", "vector_spec", "get_session"]
