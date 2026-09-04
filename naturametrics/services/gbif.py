"""GBIF occurrences as a live, browser-driven vector layer.

The third live third-party feed in this app, after services/embargos.py and
services/auto_infracao.py, and it plugs into exactly the same per-viewport
dynamic-vector pipeline — ``"dynamic": True`` + ``west/south/east/north``,
refetched on every map "settle". See embargos.py's docstring for the shape of
that pipeline; components/map/leaflet_map.js needed no new fetching code for
this layer either.

Two things genuinely differ from the IBAMA services, and both come from the
API's own measurements (config/gbif.py records why the REST API was chosen over
the BigQuery public dataset in the first place):

**The response must be slimmed here, not in the browser.** One page of 300
occurrences is 2.2 MB of verbatim Darwin Core off the wire. The tooltip, the
kingdom colouring and the click handler between them read 18 fields, about
200 bytes per record. Dropping the rest server-side turns a 2.2 MB payload into
roughly 60 KB, which is the whole reason this is proxied rather than fetched
directly by Leaflet — the IBAMA services proxy for CORS and paging, this one
proxies to avoid shipping 2.1 MB of unused verbatim fields per pan.

**Filters are structural, not decorative.** The IBAMA layers take a bbox and
nothing else. This one carries the whole ALA-style accordion — taxon, basis of
record, year range, UF — into the upstream query, because at zoom 10 over a
city the viewport can hold tens of thousands of records against a
GBIF_MAX_PAGES cap of a few thousand (config/settings.py — ``_fetch()`` below
pages up to that cap, concurrently, once it learns the true count). An
unfiltered layer over a real hotspot is still not a smaller version of a
filtered one; it is an arbitrary sample of whichever records happen to fall
inside the cap. ``properties.count`` and ``properties.truncated`` carry the
real total back so the panel can say "1500 of 22 400" rather than implying
what's shown is everything.

**This function must never raise**, same reasoning and same convention as
``embargos.polygons_in_bbox``: it is called silently on every map movement,
with nowhere to surface an exception, so failures come back as
``properties.error`` on an empty FeatureCollection.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Optional

import requests

from ..config import gbif as gc
from ..config.settings import (
    GBIF_CACHE_TTL_S,
    GBIF_MAX_PAGES,
    GBIF_MIN_ZOOM,
    GBIF_PAGE_SIZE,
    GBIF_TIMEOUT_CONNECT,
    GBIF_TIMEOUT_READ,
)

logger = logging.getLogger(__name__)

_TIMEOUT = (GBIF_TIMEOUT_CONNECT, GBIF_TIMEOUT_READ)

#: Path served by the backend (see naturametrics/api). Relative, like
#: embargos.GEOJSON_PATH — the map component resolves it against the backend
#: origin.
GEOJSON_PATH = "/_gbif.geojson"

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
    """The accordion's state, as the query layer sees it.

    Frozen and hashable so it can be part of a cache key directly. Every field
    is optional and empty means "no constraint" — the panel starts with nothing
    selected, and that has to mean the whole country rather than nothing at all.
    """

    taxon_key: int | None = None
    basis_of_record: tuple[str, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    gadm_gid: str = ""
    scientific_name: str = ""

    def as_params(self) -> list[tuple[str, str]]:
        """Upstream query parameters, as a list because GBIF takes repeated
        keys for multi-valued filters (``basisOfRecord`` especially) and a
        plain dict cannot express that."""
        params: list[tuple[str, str]] = [
            ("country", gc.COUNTRY),
            ("has_coordinate", "true"),
            # Records GBIF itself has flagged as having a geospatial problem —
            # a coordinate in the sea for a terrestrial taxon, a country
            # mismatch, a zero/zero pair. Excluded rather than drawn, because
            # this layer's entire purpose is telling someone what was recorded
            # *at a place*, and a flagged coordinate is precisely the record
            # that does not answer that.
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
            # `q` is GBIF's full-text field. Used rather than
            # `scientificName` because the latter demands an exact match on
            # the interpreted name including its authorship — "Panthera onca"
            # returns nothing, only "Panthera onca (Linnaeus, 1758)" does.
            params.append(("q", self.scientific_name))
        return params

    def cache_fragment(self) -> str:
        return "|".join(f"{k}={v}" for k, v in self.as_params())

    @property
    def active(self) -> bool:
        """Whether anything narrower than "all of Brazil" is selected."""
        return bool(self.taxon_key or self.basis_of_record or self.year_from
                    or self.year_to or self.gadm_gid or self.scientific_name)


def filters_from_query(params: Any) -> Filters:
    """Build :class:`Filters` from a Starlette ``QueryParams``.

    Every value is validated here rather than trusted: this is a public HTTP
    route, the values go into an upstream query string, and a bad int must
    degrade to "no filter" rather than to a 500 on every map pan.
    """
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
    valid_gids = {gid for gid, _uf, _name in gc.UF_GADM}
    gid = params.get("gadm") or ""

    return Filters(
        taxon_key=_int_or_none("taxon_key"),
        basis_of_record=basis,
        year_from=_int_or_none("year_from"),
        year_to=_int_or_none("year_to"),
        gadm_gid=gid if gid in valid_gids else "",
        # Bounded: this reaches an upstream full-text index, and an unbounded
        # string from a query param has no business being forwarded whole.
        scientific_name=(params.get("name") or "").strip()[:120],
    )


# --------------------------------------------------------------------------- #
# Short-lived cache — de-duplicates the debounced refetch bursts a pan/zoom
# produces (leaflet_map.js's "settle" handler), not a long-term store.
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
    # Rounded to 3dp (~100 m), matching the client's own rounding in
    # leaflet_map.js's specUrl — a finer key would never hit the cache at all.
    return (f"gbif:{west:.3f}:{south:.3f}:{east:.3f}:{north:.3f}"
            f":{filters.cache_fragment()}")


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def _clean(field: str, value: Any) -> Any:
    """Normalise one field value, or return ``None`` to drop it.

    Some publishers ship records with unrelated content packed into every
    field — a sync error between the collection and GBIF rather than an
    unusually long name. Left alone these break the layer in three ways: the
    tooltip stops being readable, the slimmed payload stops being slim, and a
    corrupt "kingdom" silently becomes its own slice of the map legend.

    Non-strings (the numeric ``year``, ``gbif_id``, ``coordinate_uncertainty_m``)
    pass through untouched — a bad number is still a number, and the callers
    that read them coerce anyway.
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return value

    # Newlines and tabs are what a pasted verbatim row leaves behind, and each
    # one would break the tooltip's row layout in leaflet_map.js.
    text = " ".join(value.split())
    if not text:
        return None

    if field in gc.CONTROLLED_FIELDS:
        # Dropped, never truncated — see config/gbif.py::CONTROLLED_FIELDS.
        return None if len(text) > gc.CONTROLLED_MAX_CHARS else text
    if len(text) > gc.FREETEXT_MAX_CHARS:
        return text[:gc.FREETEXT_MAX_CHARS].rstrip() + "\u2026"
    return text


def _slim(record: dict) -> dict | None:
    """One GBIF record → one GeoJSON feature, keeping only what is drawn.

    Returns ``None`` for a record with no usable coordinate. ``has_coordinate``
    already excludes those upstream, but a null slipping through would become a
    feature with ``"coordinates": [None, None]``, which Leaflet renders as an
    exception rather than as nothing.
    """
    lat = record.get(gc.LAT_FIELD)
    lon = record.get(gc.LON_FIELD)
    if lat is None or lon is None:
        return None

    props: dict[str, Any] = {}
    for source, target in gc.SLIM_FIELDS.items():
        value = _clean(target, record.get(source))
        if value is not None:
            props[target] = value

    # leaflet_map.js's point-click handler reads lat/lon off properties (its
    # `selectRef` call passes `props.lat`/`props.lon` through), so the study
    # point lands on the occurrence's own coordinate rather than on the pixel
    # that was clicked.
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
        # GBIF's range syntax is "min,max" on the coordinate fields — the same
        # bbox the IBAMA services express as an esriGeometryEnvelope.
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
            logger.warning("GBIF occurrence request failed (attempt %d): %s",
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
    """Page 1 first and alone — it is the only page that tells us ``count``,
    the true match total. Any further pages needed to reach it (up to
    GBIF_MAX_PAGES) are then fired at GBIF concurrently rather than in a
    sequential loop: each page is its own ~1.5-2 s round trip (measured), so
    a 5-page fetch done one at a time would add 6-8 s to a single pan/zoom.
    Fetched in parallel it costs roughly what one page does.

    This also means the extra cost is adaptive, not a flat multiplier: a
    viewport with 250 matching records still does exactly one request, the
    same as before GBIF_MAX_PAGES was raised.
    """
    first = _fetch_page(west, south, east, north, filters, 0)
    # GBIF reports the true match count independently of what this page
    # returned — the number the panel needs to admit how much is hidden.
    total = first.get("count", 0)
    first_results = first.get("results", [])
    features = [f for f in (_slim(r) for r in first_results) if f is not None]

    more_to_fetch = (
        len(first_results) == GBIF_PAGE_SIZE and not first.get("endOfRecords")
    )
    if more_to_fetch:
        capped_total = min(total, GBIF_MAX_PAGES * GBIF_PAGE_SIZE)
        pages_wanted = -(-capped_total // GBIF_PAGE_SIZE)  # ceil
        offsets = [p * GBIF_PAGE_SIZE for p in range(1, pages_wanted)]
        if offsets:
            with ThreadPoolExecutor(max_workers=len(offsets)) as pool:
                future_offset = {
                    pool.submit(_fetch_page, west, south, east, north,
                               filters, offset): offset
                    for offset in offsets
                }
                for future in as_completed(future_offset):
                    try:
                        payload = future.result()
                    except Exception as exc:  # noqa: BLE001
                        # One page failing should not blank out the rest —
                        # the map still shows what came back, just short of
                        # the cap, same as any other truncation.
                        logger.warning(
                            "GBIF page at offset %d failed: %s",
                            future_offset[future], exc)
                        continue
                    features.extend(
                        f for f in (_slim(r) for r in payload.get("results", []))
                        if f is not None
                    )

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
        logger.warning("GBIF occurrence query failed for %s: %s", key, exc)
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
                min_zoom: int | None = None, z_index: int = 27) -> dict:
    """Spec for the dynamic, browser-fetched GBIF layer.

    One z_index above auto_infracao (26), which is itself one above embargos
    (25): the biodiversity dots are the newest and most specific reading of a
    place, and are the ones a user turns this layer on to see.

    Purely declarative, like every other vector_spec here — the fetch happens
    in the browser via leaflet_map.js's generic dynamic-layer pipeline. The
    filters ride along in ``query``, which that pipeline already forwards
    (its ``specUrl``) and already includes in its per-layer refetch key, so
    changing a filter refetches exactly as a pan does.
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
        "id": "gbif_occurrences",
        "path": GEOJSON_PATH,
        "dynamic": True,
        "query": query,
        "min_zoom": GBIF_MIN_ZOOM if min_zoom is None else min_zoom,
        "z_index": z_index,
        "opacity": opacity,
        "attribution": gc.ATTRIBUTION,
        # Coloured per feature by kingdom rather than one flat colour — see
        # leaflet_map.js's styleFor(), which this layer is the first *point*
        # layer to use (embargos and auto_infracao both take a single
        # default_color).
        "color_property": "kingdom",
        "palette": gc.KINGDOM_COLORS,
        "default_color": gc.DEFAULT_COLOR,
        # Clicking a GBIF dot pins its own details open (leaflet_map.js's
        # click-popup) rather than recentring the study area the way a plain
        # map click does — landing 4 km from a jaguar sighting because you
        # tried to read its record would answer a different question.
        # Recentring on a record's own coordinate is still possible — click
        # the map right beside the dot rather than the dot itself — a
        # dedicated "select this point" button inside the popup was tried
        # and dropped: the popup sits on a viewport-refetched dynamic layer,
        # and closing the gap between "click lands on the dot" and "the
        # button in its popup is still there to click" turned out to need
        # more surgery on the shared dynamic-layer refresh machinery than
        # the feature was worth.
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
            {"label": "Nome cient.", "property": "scientific_name"},
            {"label": "Reino", "property": "kingdom"},
            {"label": "Classe", "property": "class_name"},
            {"label": "Família", "property": "family"},
            {"label": "Data", "property": "event_date"},
            {"label": "Base do reg.", "property": "basis_of_record"},
            {"label": "Regist. por", "property": "recorded_by"},
            {"label": "Instituição", "property": "institution_code"},
            {"label": "Conj. dados", "property": "dataset_name"},
            {"label": "Incerteza(m)", "property": "coordinate_uncertainty_m"},
            {"label": "Registro", "property": "gbif_url", "link": True,
             "link_text": "Ver no GBIF ↗"},
        ],
    }


__all__ = ["GEOJSON_PATH", "Filters", "filters_from_query", "points_in_bbox",
           "vector_spec", "get_session"]
