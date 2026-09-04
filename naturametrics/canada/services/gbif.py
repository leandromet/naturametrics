"""GBIF occurrences as a live, browser-driven vector layer — the Canada page.

Same pipeline as the Brazil page's ``services/gbif.py`` (dynamic vector spec,
server-side slimming, structural filters, never-raises contract) — see that
file's docstring for the full rationale, none of which is country-specific.
Only two things differ here: this queries ``country=CA`` instead of ``BR``
(via ``canada/config/gbif.py``), and it is served from its own path,
``GEOJSON_PATH``, since both pages share one Starlette app and route paths
are global.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from ...config.settings import (
    GBIF_CACHE_TTL_S,
    GBIF_MAX_PAGES,
    GBIF_MIN_ZOOM,
    GBIF_PAGE_SIZE,
    GBIF_TIMEOUT_CONNECT,
    GBIF_TIMEOUT_READ,
)
from ..config import gbif as gc

logger = logging.getLogger(__name__)

_TIMEOUT = (GBIF_TIMEOUT_CONNECT, GBIF_TIMEOUT_READ)

#: Distinct from the Brazil page's "/_gbif.geojson" — one Starlette app serves
#: both pages, so the two routes cannot share a path.
GEOJSON_PATH = "/_gbif_ca.geojson"

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update({
                    "User-Agent": gc.USER_AGENT,
                    "Accept": "application/json",
                })
                _session = s
    return _session


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Filters:
    """The accordion's state, as the query layer sees it — the Canada page's
    own copy of the Brazil page's ``Filters``, carrying ``country=CA`` instead
    of ``BR`` in :meth:`as_params`. Everything else is identical; see the
    Brazil ``services/gbif.py::Filters`` docstring."""

    taxon_key: int | None = None
    basis_of_record: tuple[str, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    gadm_gid: str = ""
    scientific_name: str = ""

    def as_params(self) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [
            ("country", gc.COUNTRY),
            ("has_coordinate", "true"),
            ("has_geospatial_issue", "false"),
        ]
        if self.taxon_key:
            params.append(("taxonKey", str(self.taxon_key)))
        for basis in self.basis_of_record:
            params.append(("basisOfRecord", basis))
        if self.year_from or self.year_to:
            lo = self.year_from or gc.YEAR_MIN
            hi = self.year_to or time.gmtime().tm_year
            params.append(("year", f"{lo},{hi}"))
        if self.gadm_gid:
            params.append(("gadmGid", self.gadm_gid))
        if self.scientific_name:
            params.append(("q", self.scientific_name))
        return params

    def cache_fragment(self) -> str:
        return "|".join(f"{k}={v}" for k, v in self.as_params())

    @property
    def active(self) -> bool:
        """Whether anything narrower than "all of Canada" is selected."""
        return bool(self.taxon_key or self.basis_of_record or self.year_from
                    or self.year_to or self.gadm_gid or self.scientific_name)


def filters_from_query(params: Any) -> Filters:
    """Build :class:`Filters` from a Starlette ``QueryParams`` — validated the
    same way as the Brazil page's ``filters_from_query``: a public route whose
    values reach a third-party query string, so a bad value degrades to "no
    filter" rather than a 500 on every map pan."""
    def _int_or_none(name: str) -> int | None:
        raw = params.get(name)
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    valid_basis = {code for code, _pt, _en in gc.BASIS_OF_RECORD}
    basis = tuple(
        b for b in (params.get("basis") or "").split(",")
        if b and b in valid_basis
    )
    valid_gids = {gid for gid, _pt, _name in gc.PROVINCE_GADM}
    gid = params.get("gadm") or ""

    return Filters(
        taxon_key=_int_or_none("taxon_key"),
        basis_of_record=basis,
        year_from=_int_or_none("year_from"),
        year_to=_int_or_none("year_to"),
        gadm_gid=gid if gid in valid_gids else "",
        scientific_name=(params.get("name") or "").strip()[:120],
    )


# --------------------------------------------------------------------------- #
# Short-lived cache — same purpose as the Brazil page's: de-duplicates the
# debounced refetch bursts a pan/zoom produces, not a long-term store.
# --------------------------------------------------------------------------- #
@dataclass
class _Entry:
    value: Any
    stored_at: float

    def fresh(self) -> bool:
        return (time.time() - self.stored_at) < GBIF_CACHE_TTL_S


_cache: dict[str, _Entry] = {}
_cache_lock = threading.Lock()


def _bbox_key(west: float, south: float, east: float, north: float,
              filters: Filters) -> str:
    return (f"gbif_ca:{west:.3f}:{south:.3f}:{east:.3f}:{north:.3f}"
            f":{filters.cache_fragment()}")


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def _clean(field: str, value: Any) -> Any:
    """Same normalisation as the Brazil page's ``_clean`` — see that file for
    why a controlled field is dropped rather than truncated."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return value

    text = " ".join(value.split())
    if not text:
        return None

    if field in gc.CONTROLLED_FIELDS:
        return None if len(text) > gc.CONTROLLED_MAX_CHARS else text
    if len(text) > gc.FREETEXT_MAX_CHARS:
        return text[:gc.FREETEXT_MAX_CHARS].rstrip() + "…"
    return text


def _slim(record: dict) -> dict | None:
    lat = record.get(gc.LAT_FIELD)
    lon = record.get(gc.LON_FIELD)
    if lat is None or lon is None:
        return None

    props: dict[str, Any] = {}
    for source, target in gc.SLIM_FIELDS.items():
        value = _clean(target, record.get(source))
        if value is not None:
            props[target] = value

    props["lat"] = lat
    props["lon"] = lon
    # The canonical page for this exact record — "key" is GBIF's own
    # occurrence id, stable across the API and the website, so this is the
    # one link that reliably lands on the record itself rather than a search
    # for it.
    gbif_id = props.get("gbif_id")
    if gbif_id is not None:
        props["gbif_url"] = f"{gc.PORTAL_URL}/occurrence/{gbif_id}"

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def _fetch_page(west: float, south: float, east: float, north: float,
                filters: Filters, offset: int) -> dict:
    params = filters.as_params()
    params.extend([
        ("decimalLatitude", f"{south},{north}"),
        ("decimalLongitude", f"{west},{east}"),
        ("limit", str(GBIF_PAGE_SIZE)),
        ("offset", str(offset)),
    ])

    session = get_session()
    last: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            r = session.get(gc.OCCURRENCE_SEARCH, params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            last = exc
            logger.warning("GBIF CA occurrence request failed (attempt %d): %s",
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
    raise RuntimeError(f"GBIF occurrence service unreachable: {last}")


def _fetch(west: float, south: float, east: float, north: float,
           filters: Filters) -> dict:
    features: list[dict] = []
    total = 0
    for page in range(GBIF_MAX_PAGES):
        payload = _fetch_page(west, south, east, north, filters,
                              page * GBIF_PAGE_SIZE)
        total = payload.get("count", 0)
        results = payload.get("results", [])
        features.extend(f for f in (_slim(r) for r in results) if f is not None)
        if payload.get("endOfRecords") or len(results) < GBIF_PAGE_SIZE:
            break

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "count": total,
            "shown": len(features),
            "truncated": total > len(features),
            "filtered": filters.active,
        },
    }


def points_in_bbox(west: float, south: float, east: float, north: float,
                   filters: Filters | None = None) -> dict:
    """GBIF occurrences inside a viewport, as slim GeoJSON. Never raises."""
    filters = filters or Filters()
    key = _bbox_key(west, south, east, north, filters)
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and hit.fresh():
            return hit.value

    try:
        value = _fetch(west, south, east, north, filters)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GBIF CA occurrence query failed for %s: %s", key, exc)
        value = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"error": str(exc), "count": 0, "shown": 0,
                           "truncated": False, "filtered": filters.active},
        }

    with _cache_lock:
        _cache[key] = _Entry(value, time.time())
    return value


# --------------------------------------------------------------------------- #
# Layer spec
# --------------------------------------------------------------------------- #
def vector_spec(filters: Filters, opacity: float = 0.85,
                min_zoom: int | None = None, z_index: int = 25) -> dict:
    """Spec for the dynamic, browser-fetched GBIF layer.

    ``z_index=25`` puts it above every other Canada overlay (Hansen change
    tops out at 20): the biodiversity dots are the newest and most specific
    reading of a place, same reasoning as the Brazil page's own placement one
    above its own topmost overlay.

    ``id`` is prefixed ``ca:`` to match every other id this page's
    ``CanadaLayersMixin`` mints (``ca:aci:...``, ``ca:hansen_tc:...``) — purely
    cosmetic, since this component tree and state are entirely separate from
    the Brazil page's, but it keeps a mixed log line unambiguous.
    """
    query: dict[str, str] = {}
    if filters.taxon_key:
        query["taxon_key"] = str(filters.taxon_key)
    if filters.basis_of_record:
        query["basis"] = ",".join(filters.basis_of_record)
    if filters.year_from:
        query["year_from"] = str(filters.year_from)
    if filters.year_to:
        query["year_to"] = str(filters.year_to)
    if filters.gadm_gid:
        query["gadm"] = filters.gadm_gid
    if filters.scientific_name:
        query["name"] = filters.scientific_name

    return {
        "id": "ca:gbif_occurrences",
        "path": GEOJSON_PATH,
        "dynamic": True,
        "query": query,
        "min_zoom": GBIF_MIN_ZOOM if min_zoom is None else min_zoom,
        "z_index": z_index,
        "opacity": opacity,
        "attribution": gc.ATTRIBUTION,
        "color_property": "kingdom",
        "palette": gc.KINGDOM_COLORS,
        "default_color": gc.DEFAULT_COLOR,
        # See the Brazil page's own vector_spec for the full rationale: a
        # click pins this occurrence's details open instead of recentring the
        # study area — click the map beside the dot to recentre there instead.
        # A dedicated in-popup "select this point" button was tried and
        # dropped there; see that file's comment for why.
        "point_style": {
            "radius": 4,
            "color": "#ffffff",
            "weight": 1,
            "fillOpacity": opacity,
        },
        "hover_style": {
            "radius": 7,
            "color": "#ffffff",
            "weight": 1.5,
            "fillOpacity": 1.0,
        },
        "tooltip": [
            {"label": "Scientific name", "property": "scientific_name"},
            {"label": "Kingdom", "property": "kingdom"},
            {"label": "Class", "property": "class_name"},
            {"label": "Family", "property": "family"},
            {"label": "Date", "property": "event_date"},
            {"label": "Basis of record", "property": "basis_of_record"},
            {"label": "Recorded by", "property": "recorded_by"},
            {"label": "Institution", "property": "institution_code"},
            {"label": "Dataset", "property": "dataset_name"},
            {"label": "Uncertainty (m)", "property": "coordinate_uncertainty_m"},
            {"label": "Record", "property": "gbif_url", "link": True,
             "link_text": "View on GBIF ↗"},
        ],
    }


__all__ = ["GEOJSON_PATH", "Filters", "filters_from_query", "points_in_bbox",
           "vector_spec", "get_session"]
