"""Runtime settings, read from the environment with sane local defaults.

Every value here is overridable by an env var so the same image runs locally and
on Cloud Run (decision D10) without a code change.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------- #
# Earth Engine
# --------------------------------------------------------------------------- #
#: Decision D5: the Partner tier authorisation is granted to this project
#: specifically. A different project would silently fall back to contributor
#: limits, and the fan-out design assumes Partner concurrency.
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "ee-leandromet")

#: 'partner' | 'contributor'. Sizes the EE thread pool. Everything must still
#: work at 'contributor' — just slower (D5).
EE_TIER = os.environ.get("NM_EE_TIER", "partner").strip().lower()

#: Hard ceiling on simultaneous Earth Engine requests.
EE_CONCURRENCY = _int("NM_EE_CONCURRENCY", 64 if EE_TIER == "partner" else 4)

EE_MAX_PIXELS = int(1e10)
EE_TILE_SCALE = _int("NM_EE_TILE_SCALE", 4)
EE_DEFAULT_SCALE_M = _int("NM_EE_SCALE_M", 30)

#: EE tile URLs carry a signed component and expire. Re-mint before they do.
TILE_CACHE_TTL_SECONDS = _int("NM_TILE_CACHE_TTL", 3600)
TILE_CACHE_MAX_ENTRIES = _int("NM_TILE_CACHE_MAX", 512)

# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
BUFFER_RADII_KM: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0)

#: D2: cumulative discs by default ("everything within N km"), rings as a toggle.
BUFFER_MODE_DEFAULT = os.environ.get("NM_BUFFER_MODE", "disc")

#: D6/D10: Hansen tree-cover % defining forest for the disturbance bound.
HANSEN_TREECOVER_THRESHOLD = _int("NM_HANSEN_TREECOVER_THRESHOLD", 30)

#: Generous bbox around Brazil — used to reject clicks MapBiomas cannot answer.
BRAZIL_BBOX = (-74.5, -34.5, -33.5, 6.5)  # min_lon, min_lat, max_lon, max_lat

# --------------------------------------------------------------------------- #
# Feature flags
# --------------------------------------------------------------------------- #
#: SPOT 2008 requires accepting a licence agreement, granted to the service
#: account that runs the app. Fail closed with an explanation, never a traceback.
SPOT_ENABLED = _bool("NM_SPOT_ENABLED", False)

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
IFN_CATALOG_PATH = Path(
    os.environ.get("NM_IFN_CATALOG", str(REPO_ROOT / "data" / "ifn_points.csv"))
)

#: Precomputed (região, UF, município, bioma) groups with counts and bounding
#: boxes — everything the filter UI needs without an Earth Engine round trip.
#: Built by scripts/join_ifn_biomes.py; committed, because a deploy has no way
#: to rebuild it before the first request.
IFN_FILTER_INDEX_PATH = Path(
    os.environ.get("NM_IFN_FILTER_INDEX",
                   str(REPO_ROOT / "data" / "ifn_filter_index.csv"))
)

#: One row per conglomerado with its coordinates and biome. Backs the
#: interactive hover/click layer (answering "what is in this viewport" locally,
#: with no round trip) and enumerates what an export covers. Same origin and the
#: same commit rationale as the index above.
IFN_POINTS_TABLE_PATH = Path(
    os.environ.get("NM_IFN_POINTS_TABLE",
                   str(REPO_ROOT / "data" / "ifn_points_biome.csv"))
)

# --------------------------------------------------------------------------- #
# Interactive conglomerado layer
# --------------------------------------------------------------------------- #
#: Below this zoom the conglomerados are tiles only — pretty, and not clickable.
#: At or above it the points in view are also served as real geometry so they can
#: be hovered and clicked. 8 frames roughly one state, where the count in view is
#: in the hundreds rather than the thousands.
IFN_INTERACTIVE_MIN_ZOOM = _int("NM_IFN_INTERACTIVE_MIN_ZOOM", 8)

#: Hard ceiling on points returned for one viewport. Protects the browser from a
#: pathological view (zoom 8 over São Paulo) rather than the server, which reads
#: this from memory.
IFN_VIEWPORT_LIMIT = _int("NM_IFN_VIEWPORT_LIMIT", 1500)

# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
#: Single-pixel export is one streamed Earth Engine download and is effectively
#: free at any size — measured 17 479 points × 40 years = 2.3 MB in 1.9 s — so it
#: is not capped.
#:
#: The buffer export is not free: it fans the full per-point analysis out across
#: the Earth Engine pool at ~0.11 s/point (measured, Partner tier) and produces
#: ~600 rows per conglomerado.
#:
#: The binding constraint is the spreadsheet, not us. A sheet holds 1 048 576
#: rows, so ~1 750 conglomerados is the most that can be written without silently
#: losing the tail. 1 500 leaves headroom and costs about three minutes.
#: The whole grid (17 479) would be ~10.5 M rows and half an hour — that is a
#: batch job, not a button, and the UI says so rather than pretending.
EXPORT_BUFFER_MAX_POINTS = _int("NM_EXPORT_BUFFER_MAX_POINTS", 1500)

#: Per-point timeout inside the fan-out. One slow conglomerado must not hold the
#: whole export.
EXPORT_POINT_TIMEOUT_S = _int("NM_EXPORT_POINT_TIMEOUT", 180)

# --------------------------------------------------------------------------- #
# Map defaults
# --------------------------------------------------------------------------- #
#: Framed on Brazil rather than on South America — at zoom 4 roughly half the
#: canvas was ocean and Pacific. Brazil spans lon -74..-34, lat -34..5, so zoom 5
#: centred here fills the map pane with the country.
MAP_CENTER: tuple[float, float] = (
    _float("NM_MAP_CENTER_LAT", -14.5),
    _float("NM_MAP_CENTER_LON", -53.5),
)
MAP_ZOOM = _int("NM_MAP_ZOOM", 5)

#: Initial framing, as [[south, west], [north, east]]. Slightly wider than
#: Brazil's true extent (lon -73.99..-32.39, lat -33.75..5.27) so the outline is
#: not flush against the edge. Used with Leaflet fitBounds, so it frames correctly
#: on any viewport instead of relying on a zoom level tuned to one screen size.
BRAZIL_VIEW_BOUNDS: tuple[tuple[float, float], tuple[float, float]] = (
    (-34.5, -74.5),
    (6.0, -33.0),
)

DEFAULT_LANGUAGE = os.environ.get("NM_LANGUAGE", "pt")
SUPPORTED_LANGUAGES = ("pt", "en")
