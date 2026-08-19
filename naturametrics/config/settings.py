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
#: SPOT 2008 requires accepting a licence agreement, granted per service
#: account. Verified working for this project's account on 2026-08-19 (both the
#: VISUAL and ANALYTIC mosaics mint tile URLs), so the default is now on and the
#: flag is the kill switch for a deployment whose account lacks the grant.
#: Fail closed with an explanation, never a traceback.
SPOT_ENABLED = _bool("NM_SPOT_ENABLED", True)

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
# Multiple selection
# --------------------------------------------------------------------------- #
#: Ceiling on conglomerados picked by hand. Each click costs one Earth Engine
#: call (~0.5 s) and its history stays in memory so the chart and the export
#: never recompute it, so the real limits are the map getting unreadable and the
#: aggregate losing meaning — both of which arrive well before 200.
MULTI_SELECT_MAX_POINTS = _int("NM_MULTI_SELECT_MAX", 200)

# --------------------------------------------------------------------------- #
# Buffer land-cover preview
# --------------------------------------------------------------------------- #
#: When a point is hovered or selected, the MapBiomas layer is shown *inside* its
#: largest buffer and nowhere else. This costs no Earth Engine call at all: the
#: tile URL for every year is already minted by the startup prefetch, and the
#: restriction to the buffer is a CSS clip applied in the browser — the same
#: technique as the swipe divider (doc/06 §5b).
BUFFER_PREVIEW_RADIUS_KM = _float("NM_BUFFER_PREVIEW_RADIUS_KM",
                                  max(BUFFER_RADII_KM))
BUFFER_PREVIEW_OPACITY = _float("NM_BUFFER_PREVIEW_OPACITY", 0.70)

#: 'circle' | 'bbox'. A circle is what the buffer actually is, and costs the same
#: to draw. The bbox exists as an escape hatch: clipping in a Leaflet layer
#: container is fiddly (its reference box is 0×0 — see leaflet_map.js), and if
#: `clip-path: circle()` ever misbehaves on some browser, the rectangle uses the
#: legacy `clip: rect()` path that the swipe divider has already proven.
BUFFER_PREVIEW_SHAPE = os.environ.get("NM_BUFFER_PREVIEW_SHAPE", "circle")

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
#: The buffer export fans the full per-point analysis out across the Earth Engine
#: pool. Measured on 40 conglomerados spread over MT/BA/RS/AM — deliberately a
#: mix of landscapes, because the row count tracks class diversity and a sample
#: from one município badly understates it:
#:
#:     radius   rows/point  mean / p90 / max
#:      1 km          158 /  249 /  341
#:      2 km          205 /  ~   /  368
#:      5 km          284 /  ~   /  480
#:     10 km          350 /  437 /  553
#:     all four       997 / 1406 / 1677
#:
#: Budget per radius, a little above p90. An underestimate is not fatal — the
#: writer splits an oversized sheet rather than failing — so these are tuned for
#: a usable ceiling rather than for the worst landscape in Brazil.
EXPORT_ROWS_PER_POINT: dict[float, int] = {1.0: 280, 2.0: 330, 5.0: 430, 10.0: 500}

#: Each radius gets **its own tab**, so the spreadsheet's row limit applies per
#: radius instead of to all four together — four times the capacity, and a tab
#: per radius is what the study-point workbook already does.
#: 1 048 576 is the hard limit in LibreOffice and Excel; this leaves headroom.
EXPORT_ODS_ROWS_PER_SHEET = _int("NM_EXPORT_ROWS_PER_SHEET", 1_000_000)

#: Measured cost of one buffer row in the finished ODS: **46 bytes**, flat from
#: 200 k to 1 M rows (9.2 / 23.0 / 46.0 MB). Measured with realistic values —
#: areas rounded to 4 dp, real class and município names. Random unrounded
#: doubles measure 61 B/row and are not what the export writes.
EXPORT_BYTES_PER_ROW = _int("NM_EXPORT_BYTES_PER_ROW", 46)

#: Hard ceiling on a **buffer** export, in conglomerados.
#:
#: Unlike the file-size caps this replaces, it has a reason that comes from the
#: data rather than from feel: it clears the largest biome, so any single-biome
#: selection fits whole. Measured against the point table —
#:
#:     Amazônia 5 801 · Cerrado 4 898 · Mata Atlântica 3 511
#:     Caatinga 2 367 · Pampa 523 · Pantanal 374   (largest UF: PA, 1 884)
#:
#: — so 6 000 covers every biome and every state with room to spare, and costs
#: about 12 minutes at the measured 0.12 s/conglomerado. Past that the useful
#: unit is the whole grid, which is a batch job rather than a button.
#:
#: The **pixel** and **point-list** halves are deliberately NOT capped: they do
#: all 17 479 conglomerados in about two seconds.
EXPORT_MAX_BUFFER_POINTS = _int("NM_EXPORT_MAX_BUFFER_POINTS", 6000)

#: Size at which the panel starts warning. **Advisory only — nothing is
#: refused.** There is no size limit on an ODS file, and inventing one would be
#: making up a constraint that does not exist; the only hard limit in the format
#: is rows per sheet, and an oversized sheet is split rather than refused.
#:
#: What is real, and worth warning about: ``rx.download`` delivers the file as a
#: base64 ``data:`` URI inside the WebSocket event, so a large export is held in
#: memory whole — once on the server, once as base64, once again in the browser —
#: and very large data URIs are handled poorly by some browsers.
EXPORT_WARN_FILE_MB = _int("NM_EXPORT_WARN_FILE_MB", 25)

#: For the "this will take about…" estimate. Measured between 0.06 and 0.14
#: s/point depending on how warm Earth Engine is; the high end is quoted so the
#: estimate errs towards over-promising the wait rather than under.
EXPORT_SECONDS_PER_POINT = _float("NM_EXPORT_SECONDS_PER_POINT", 0.12)

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
