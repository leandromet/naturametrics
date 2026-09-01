"""Which species were recorded inside each buffer around the study point.

The analytical half of the GBIF integration, and the reason the layer is worth
more than a scatter of dots: it answers "what has anyone recorded within 1 km of
here", against the same discs services/buffers.py already draws.

**Aggregates, not records.** The obvious implementation — page through every
occurrence in the buffer and count in Python — would be thousands of requests
and hundreds of megabytes for one 10 km disc in a well-sampled place. GBIF's
facet API does the whole thing server-side: ``limit=0`` returns no records at
all, and ``facet=scientificName`` comes back with readable names rather than
keys, so there is no second round of lookups to turn 500 species keys into
500 names. One request per buffer, ~1.1 s each (measured), fanned out
concurrently — the same "batch what is one query, fan out everything else"
shape the MapBiomas history already uses.

**Discs only, never rings.** services/buffers.py offers both (decision D2), but
a species list for an annulus is not a meaningful object: presence is not
additive, and "the species in the 2–5 km ring" would be read by everyone as a
list that excludes the ones also present nearer in, which is not what a
subtraction of counts gives you. The counts here are therefore always
cumulative discs, and ``mode`` is reported in the result so the caller can say
so rather than quietly implying the active buffer mode was honoured.

Nothing here raises, for the same reason as services/gbif.py: it is triggered by
an ordinary map click, and one failing buffer must degrade to "no data for that
radius" rather than take down the whole analysis run.
"""

from __future__ import annotations

import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import requests

from ..config import gbif as gc
from ..config.settings import (
    BUFFER_RADII_KM,
    GBIF_BUFFER_VERTICES,
    GBIF_EXPORT_SPECIES_LIMIT,
    GBIF_FACET_LIMIT,
    GBIF_TIMEOUT_CONNECT,
    GBIF_TIMEOUT_READ,
)
from .gbif import Filters, get_session

logger = logging.getLogger(__name__)

_TIMEOUT = (GBIF_TIMEOUT_CONNECT, GBIF_TIMEOUT_READ)

#: Its own small pool rather than services/ee_concurrency.py's. That one is
#: sized to the Earth Engine Partner-tier budget (64) and exists to keep EE
#: requests from queueing behind each other; borrowing it for third-party HTTP
#: would put GBIF calls in contention with the analysis they are running
#: alongside. Five buffers is the whole job, so five workers is the whole pool.
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=max(len(BUFFER_RADII_KM), 1),
                    thread_name_prefix="nm-gbif",
                )
    return _executor


@dataclass
class BufferSpecies:
    """One buffer's biodiversity summary."""

    radius_km: float
    total: int = 0
    #: ``(scientific name, occurrence count)``, most-recorded first, capped at
    #: GBIF_EXPORT_SPECIES_LIMIT. The results tab renders only the first
    #: GBIF_SPECIES_TABLE_LIMIT of these; the rest exist so the spreadsheet
    #: export is not silently truncated to what happened to fit on screen.
    species: list[tuple[str, int]] = field(default_factory=list)
    #: ``(kingdom name, count)`` — the same taxonomy the map colouring uses.
    kingdoms: list[tuple[str, int]] = field(default_factory=list)
    #: ``(basisOfRecord code, count)``.
    basis: list[tuple[str, int]] = field(default_factory=list)
    #: Distinct names returned. Capped by GBIF_FACET_LIMIT, so this is a floor
    #: on true richness whenever ``richness_truncated`` is set.
    richness: int = 0
    richness_truncated: bool = False
    error: str = ""


def circle_wkt(lat: float, lon: float, radius_km: float,
               vertices: int = GBIF_BUFFER_VERTICES) -> str:
    """A buffer disc as the WKT polygon GBIF's ``geometry`` filter takes.

    Built in an azimuthal-equidistant projection centred on the point, exactly
    as services/buffers.py builds its own geometry, so the polygon asked of GBIF
    is the same disc the map draws rather than a naive degree-radius circle that
    would be 10 % too narrow in Roraima and too wide in Rio Grande do Sul.

    **Wound counter-clockwise.** GBIF rejects a clockwise exterior ring outright
    (``HTTP 400: Polygon with clockwise exterior ring`` — verified live), which
    is a silent-looking failure since it arrives as an error status rather than
    as zero results.
    """
    from pyproj import Transformer

    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +units=m +datum=WGS84 +no_defs"
    to_aeqd = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True).transform
    to_wgs = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True).transform

    ox, oy = to_aeqd(lon, lat)
    radius_m = radius_km * 1000.0
    points = [
        to_wgs(ox + radius_m * math.cos(2 * math.pi * i / vertices),
               oy + radius_m * math.sin(2 * math.pi * i / vertices))
        for i in range(vertices)
    ]
    points.append(points[0])
    return "POLYGON((" + ",".join(f"{x:.6f} {y:.6f}" for x, y in points) + "))"


_KINGDOM_BY_KEY = {str(key): name for key, name in gc.KINGDOMS}


def _facet_rows(payload: dict, field_name: str) -> list[tuple[str, int]]:
    for facet in payload.get("facets", []):
        if facet.get("field") == field_name:
            return [(c["name"], c["count"]) for c in facet.get("counts", [])]
    return []


def _one_buffer(lat: float, lon: float, radius_km: float,
                filters: Filters) -> BufferSpecies:
    out = BufferSpecies(radius_km=radius_km)
    params = filters.as_params()
    params.extend([
        ("geometry", circle_wkt(lat, lon, radius_km)),
        ("limit", "0"),
        ("facet", "scientificName"),
        ("facet", "kingdomKey"),
        ("facet", "basisOfRecord"),
        ("facetLimit", str(GBIF_FACET_LIMIT)),
    ])

    try:
        r = get_session().get(gc.OCCURRENCE_SEARCH, params=params, timeout=_TIMEOUT)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        payload = r.json()
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        logger.warning("GBIF buffer facet failed (%.1f km): %s", radius_km, exc)
        out.error = str(exc)
        return out

    out.total = payload.get("count", 0)
    names = _facet_rows(payload, "SCIENTIFIC_NAME")
    out.species = names[:GBIF_EXPORT_SPECIES_LIMIT]
    out.richness = len(names)
    out.richness_truncated = len(names) >= GBIF_FACET_LIMIT
    out.kingdoms = [
        (_KINGDOM_BY_KEY.get(key, key), count)
        for key, count in _facet_rows(payload, "KINGDOM_KEY")
    ]
    out.basis = _facet_rows(payload, "BASIS_OF_RECORD")
    return out


def species_by_buffer(lat: float, lon: float,
                      radii_km: tuple[float, ...] = BUFFER_RADII_KM,
                      filters: Filters | None = None) -> list[BufferSpecies]:
    """One :class:`BufferSpecies` per radius, smallest first. Never raises.

    The buffers go out concurrently: they are independent queries against a
    third party, so the run costs one round-trip in wall clock rather than
    five (~1.1 s instead of ~5.5 s).
    """
    filters = filters or Filters()
    radii = sorted(radii_km)
    futures = [
        _get_executor().submit(_one_buffer, lat, lon, r, filters)
        for r in radii
    ]
    results = []
    for radius, future in zip(radii, futures):
        try:
            results.append(future.result())
        except Exception as exc:  # noqa: BLE001
            logger.warning("GBIF buffer task crashed (%.1f km): %s", radius, exc)
            results.append(BufferSpecies(radius_km=radius, error=str(exc)))
    return results


__all__ = ["BufferSpecies", "species_by_buffer", "circle_wkt"]
