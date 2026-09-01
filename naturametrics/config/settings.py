"""Runtime settings, read from the environment with sane local defaults.

Every value here is overridable by an env var so the same image runs locally and
on Cloud Run (decision D10) without a code change.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .vegetation_age import CENSORED_AGE

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

#: GA4 Measurement ID, shared with the portal and the other three subdomains
#: (same registrable domain umaterra.com.br, one unified property). Empty in
#: local dev so testing never pollutes real traffic data.
GA_MEASUREMENT_ID = os.environ.get("NM_GA_MEASUREMENT_ID", "")

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
BUFFER_RADII_KM: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0, 10.0)

#: D2: cumulative discs by default ("everything within N km"), rings as a toggle.
BUFFER_MODE_DEFAULT = os.environ.get("NM_BUFFER_MODE", "disc")

#: D6/D10: Hansen tree-cover % defining forest for the disturbance bound.
HANSEN_TREECOVER_THRESHOLD = _int("NM_HANSEN_TREECOVER_THRESHOLD", 30)

#: Generous bbox around Brazil — used to reject clicks MapBiomas cannot answer.
BRAZIL_BBOX = (-74.5, -34.5, -33.5, 6.5)  # min_lon, min_lat, max_lon, max_lat

# --------------------------------------------------------------------------- #
# Location search (services.geocode, services.municipios)
# --------------------------------------------------------------------------- #
#: Nominatim's usage policy: identify the app, cap request volume, stay inside
#: Brazil. See services/geocode.py — the geocoder is the last-resort resolver,
#: tried only after a coordinate and a município have both failed to match.
GEOCODER_URL = os.environ.get(
    "NM_GEOCODER_URL", "https://nominatim.openstreetmap.org/search"
)
GEOCODER_ENABLED = _bool("NM_GEOCODER_ENABLED", True)
GEOCODER_USER_AGENT = os.environ.get(
    "NM_GEOCODER_USER_AGENT",
    "naturametrics/1.0 (contact: leandromet@gmail.com)",
)
GEOCODER_TIMEOUT_CONNECT = _int("NM_GEOCODER_TIMEOUT_CONNECT", 10)
GEOCODER_TIMEOUT_READ = _int("NM_GEOCODER_TIMEOUT_READ", 20)
GEOCODER_COUNTRY_CODES = "br"

# --------------------------------------------------------------------------- #
# Drawn / uploaded study region (services.region_geometry)
# --------------------------------------------------------------------------- #
#: Ceiling on a region's own area — protects the reduceRegions calls from a
#: pathologically large polygon (a whole biome pasted by mistake) rather than
#: from a realistic study area. 20 000 km² is comparable to a large município,
#: well above the ~314 km² of the largest point buffer (10 km disc) but far
#: short of "an entire state".
GEOMETRY_MAX_AREA_KM2 = _float("NM_GEOMETRY_MAX_AREA_KM2", 20_000.0)

#: Ceiling on vertex count — protects the size of the geometry payload sent to
#: Earth Engine, same spirit as USER_POINTS_MAX_LINES below.
GEOMETRY_MAX_VERTICES = _int("NM_GEOMETRY_MAX_VERTICES", 2000)

#: Hard cap on an uploaded KML file, in bytes. Checked before the file is
#: parsed at all.
GEOMETRY_KML_MAX_BYTES = _int("NM_GEOMETRY_KML_MAX_BYTES", 2 * 1024 * 1024)

#: Not a real distance — a single-feature join key for the reduceRegions
#: parsing code shared with every buffer/full-area path, which keys its output
#: on a `radius_km` feature property. Mirrors full_area_collection's own use
#: of `max(radii_km)` as a stand-in for the same reason (services/buffers.py).
GEOMETRY_REGION_RADIUS_KM = 0.0

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
# IBAMA embargos layer (services.embargos)
# --------------------------------------------------------------------------- #
#: Same as IFN_INTERACTIVE_MIN_ZOOM — dialled back from one tick above it
#: (9) at the user's request, trading a heavier fetch at a wider viewport
#: for the layer engaging one zoom step earlier.
EMBARGOS_MIN_ZOOM = _int("NM_EMBARGOS_MIN_ZOOM", 8)

#: Short-lived: this cache exists to de-duplicate the debounced refetch bursts
#: leaflet_map.js's "map settle" handler produces, not to serve stale data —
#: upstream is IBAMA's own service, refreshed on their own schedule, not ours.
EMBARGOS_CACHE_TTL_S = _int("NM_EMBARGOS_CACHE_TTL_S", 120)

#: EMBARGOS_PAGE_SIZE matches the service's own maxRecordCount; the page count
#: caps one viewport at 4 000 features — verified live against 91 120 polygons
#: nationwide (2026-08-31), comfortable headroom over what a single-state
#: viewport past EMBARGOS_MIN_ZOOM plausibly contains.
EMBARGOS_PAGE_SIZE = _int("NM_EMBARGOS_PAGE_SIZE", 2000)
EMBARGOS_MAX_PAGES = _int("NM_EMBARGOS_MAX_PAGES", 2)

EMBARGOS_TIMEOUT_CONNECT = _int("NM_EMBARGOS_TIMEOUT_CONNECT", 10)
EMBARGOS_TIMEOUT_READ = _int("NM_EMBARGOS_TIMEOUT_READ", 30)

# --------------------------------------------------------------------------- #
# IBAMA autos de infração layer (services.auto_infracao)
# --------------------------------------------------------------------------- #
#: Infraction notices — a much denser point dataset than embargos (710 000
#: rows nationwide vs. 91 000 polygons, verified live 2026-08-31): a modest
#: bbox around a single city (Santos/SP) already maxed out one 2 000-row
#: page. Originally gated two ticks above the old EMBARGOS_MIN_ZOOM (11);
#: dialled back to match EMBARGOS_MIN_ZOOM exactly (8) at the user's
#: request — a plain point is cheap enough per feature that the much
#: higher count doesn't need its own extra margin, only the fetch/render
#: cost of whatever the page cap below actually returns, same as embargos.
AUTO_INFRACAO_MIN_ZOOM = _int("NM_AUTO_INFRACAO_MIN_ZOOM", 8)

AUTO_INFRACAO_CACHE_TTL_S = _int("NM_AUTO_INFRACAO_CACHE_TTL_S", 120)
AUTO_INFRACAO_PAGE_SIZE = _int("NM_AUTO_INFRACAO_PAGE_SIZE", 2000)
AUTO_INFRACAO_MAX_PAGES = _int("NM_AUTO_INFRACAO_MAX_PAGES", 2)

AUTO_INFRACAO_TIMEOUT_CONNECT = _int("NM_AUTO_INFRACAO_TIMEOUT_CONNECT", 10)
AUTO_INFRACAO_TIMEOUT_READ = _int("NM_AUTO_INFRACAO_TIMEOUT_READ", 30)

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

#: Rows per point *per radius* for the vegetation-age tabs (services.vegetation_
#: age), exported alongside the buffer tabs above. Unlike EXPORT_ROWS_PER_POINT
#: this is not an empirical budget — it is the structural ceiling: a histogram
#: over an age counter that tops out at CENSORED_AGE (config.vegetation_age) can
#: never have more than CENSORED_AGE distinct rows, one per possible age value,
#: no matter how varied the landscape. Measured max across 150 real points was
#: exactly that ceiling (38 as of the current DSV record), so this tracks the
#: data rather than a separate guess.
EXPORT_AGE_ROWS_PER_POINT_PER_RADIUS = CENSORED_AGE

#: Each conglomerado contributes exactly one row per radius to the change-mask
#: tab (services.change_mask.change_stats returns one loss/gain/stable row per
#: buffer) — no ceiling to derive, it is just this.
EXPORT_CHANGE_ROWS_PER_POINT_PER_RADIUS = 1

#: One summary row per radius (services.landscape_metrics.landscape_metrics) —
#: no year axis, so this is exact, not a budget.
EXPORT_LANDSCAPE_METRICS_ROWS_PER_POINT_PER_RADIUS = 1

#: One summary row per radius (services.connectivity.fragment_connectivity) —
#: same shape as the landscape-metrics tab it sits beside in the UI, exact
#: rather than a budget.
EXPORT_CONNECTIVITY_ROWS_PER_POINT_PER_RADIUS = 1

#: One row per (radius, year); not imported from services.biomass.AGB_YEARS
#: to avoid a config→services import cycle (that module already imports this
#: one) — keep in sync with its length by hand if the year list ever changes.
EXPORT_BIOMASS_ROWS_PER_POINT_PER_RADIUS = 10

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
#: about 17 minutes at the measured 0.17 s/conglomerado (land-cover history,
#: vegetation age and the change mask, fanned out together — see
#: EXPORT_SECONDS_PER_POINT). Past that the useful unit is the whole grid, which
#: is a batch job rather than a button.
#:
#: The **pixel** and **point-list** halves are deliberately NOT capped: they do
#: all 17 479 conglomerados in about two seconds.
EXPORT_MAX_BUFFER_POINTS = _int("NM_EXPORT_MAX_BUFFER_POINTS", 6000)

#: Ceiling on a pasted coordinate list (services.user_points), set equal to
#: EXPORT_MAX_BUFFER_POINTS rather than a separate number picked by feel: a
#: user-submitted list goes through the exact same buffer/age/change fan-out as
#: a conglomerado selection once "Baixar análise completa" is pressed, so the
#: same reasoning (clears the largest biome, ~17 min) applies unchanged.
USER_POINTS_MAX_LINES = EXPORT_MAX_BUFFER_POINTS

# --------------------------------------------------------------------------- #
# Abuse control (services/abuse_control.py)
# --------------------------------------------------------------------------- #
#: A dedicated bucket, separate from anything Yvynation uses — gs://naturametrics-abuse-control
#: (us-west1, uniform bucket-level access, public access prevention enforced,
#: 90-day object-deletion lifecycle rule). Cross-instance persistence is the
#: reason it exists at all: Cloud Run can and does run more than one instance,
#: and in-process rate-limit state would not coordinate across them.
ABUSE_BUCKET = os.environ.get("NM_ABUSE_BUCKET", "naturametrics-abuse-control")

#: Minimum time between one session's bulk-export runs. Keyed on the Reflex
#: client token (stable per browser tab across reconnects and page reloads),
#: not the session id, so refreshing the page does not reset it.
ABUSE_SESSION_COOLDOWN_S = _int("NM_ABUSE_SESSION_COOLDOWN_S", 300)

#: How many bulk exports one IP address may start inside the rolling window
#: below. Generous for a real user working through a few selections; the
#: point is to stop a script from queuing dozens of ~17-minute Earth Engine
#: fan-outs (doc/03-roadmap.md Phase 6 cost model) back to back.
ABUSE_IP_MAX_PER_WINDOW = _int("NM_ABUSE_IP_MAX_PER_WINDOW", 3)
ABUSE_IP_WINDOW_S = _int("NM_ABUSE_IP_WINDOW_S", 3600)

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

#: For the "this will take about…" estimate. Land-cover history alone measured
#: 0.06–0.14 s/point; once vegetation age and the change mask were folded into
#: the same buffer export (fanned out together per point, one future each), a
#: 200-point pooled measurement came to 0.171 s/point. 0.18 is quoted for a
#: little headroom, not because it was observed.
EXPORT_SECONDS_PER_POINT = _float("NM_EXPORT_SECONDS_PER_POINT", 0.18)

#: Connectivity is priced separately from EXPORT_SECONDS_PER_POINT above: it
#: is a *second* Earth Engine call (reduceToVectors) plus a local shapely
#: STRtree search per buffer (services/connectivity.py) — not part of the
#: land-cover/age/change fan-out that constant was measured from. Not yet
#: pooled at bulk-export scale; set with headroom over single-point traces
#: until a real measurement replaces it.
EXPORT_CONNECTIVITY_SECONDS_PER_POINT = _float(
    "NM_EXPORT_CONNECTIVITY_SECONDS_PER_POINT", 0.5)

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

#: Where a map click lands the viewport. The country-wide default zoom above is
#: for *finding* somewhere; once a point is picked the buffers being analysed
#: (BUFFER_RADII_KM, single-digit km) are a few pixels across at that scale, so
#: the map stayed showing half of Brazil while the panel below described a
#: neighbourhood. 8 frames the buffers and their surroundings without dropping
#: into a detail level MapBiomas' 30 m pixels cannot fill.
#:
#: A FLOOR, never a jump: `state/_point.py::set_study_point` only zooms in when
#: the map is currently wider than this, so clicking while already zoomed to a
#: field keeps that detail rather than being pulled back out to 8. That decision
#: has to happen in the browser — Python's `map_zoom` only records what it last
#: *asked* for, and nothing syncs the user's own zooming back to it.
MAP_CLICK_ZOOM = _int("NM_MAP_CLICK_ZOOM", 8)

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
