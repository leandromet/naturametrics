# 03 — Roadmap

Phases are ordered so that **every phase ends with something runnable**. Nothing here is
date-estimated; the ordering and the acceptance criteria are the useful part.

---

## Phase 0 — Foundations ✅ **COMPLETE** (2026-08-18)

**Goal:** the app boots, talks to Earth Engine, and shows a map.

- [x] `.venv` + `requirements.txt` pinned (Reflex 0.8.27, earthengine-api 1.7.40,
      plotly, shapely, pandas, python-dotenv).
- [x] `rxconfig.py`, package skeleton per [02-architecture.md](02-architecture.md) §2.
- [x] `services/ee_client.py` ported from Yvynation's `initialize_earth_engine`,
      with the three-source auth ladder. Cloud Run's env-var path is written but
      **not yet exercised** — see Phase 6.
- [x] `services/ee_concurrency.py` — EE executor (64 workers, partner profile) and
      **`tune_ee_connection_pool()`**. *Verified: pool goes 10 → 68 connections.*
- [x] `config/mapbiomas.py` — labels (PT + EN), colour map, dense 0–62 palette.
- [x] `services/tiles.py` — memoised `getMapId` with TTL, LRU bound, and
      in-flight deduplication (the fan-out design makes duplicate concurrent
      requests for one key likely, not hypothetical).
- [x] `services/layers.py` — basemap and MapBiomas layer specs + concurrent prefetch.
      *Verified: 8 years minted in 0.89 s vs ~5.1 s serial.*
- [x] **The persistent Leaflet component (D1)** — `components/map/leaflet_map.{py,js}`.
      Map created once, layers diffed in place, instance exposed as
      `container._nmMap` for fly-to and tests.
- [x] Basemap switcher (OSM / Esri Imagery / Topo / Streets).
- [x] `services/geo.py` + `tests/test_geo.py` — **coordinate-order guard** (8 tests).
      Not originally scoped; added because the click path crosses three conflicting
      conventions (Leaflet `[lat,lon]`, GeoJSON/EE `[lon,lat]`) and a swap fails
      silently rather than loudly.
- [x] `state/_point.py` — map click → validated study point. Pulled forward from
      Phase 1 to prove the event path end-to-end while D1 was still under test.

**Done when:** ✅ `reflex run` serves a full-height map of Brazil, a MapBiomas year can
be toggled from a Python-side control, and **the viewport does not move when it is**.

**Acceptance evidence** (Playwright, `scratchpad/verify_d1.py`):

| Assertion | Result |
|---|---|
| Map renders with tiles | 7 Leaflet panes, 20/20 basemap tiles loaded |
| MapBiomas layer adds | 2 layers, 40/40 tiles, attribution updated |
| **Viewport preserved across a year change** | ✅ transform identical after pan + 2× zoom |
| **EE layer genuinely re-sourced** | ✅ different `mapId` before/after |
| Console errors | 0 |
| Click accepted in Brazil / refused offshore | ✅ both, with a reason |

Visual check over Machadinho d'Oeste, RO: 1985 forest-with-fishbone → 2024
pasture-dominated, same viewport. The land-cover trajectory reads correctly.

**Two bugs found and fixed during the phase**, both worth remembering:
1. The injected JS used the `React.*` namespace, but Reflex's generated module
   imports hooks as *named* bindings — `React is not defined` at render. The
   component now declares `useEffect`/`useRef` in `add_imports` rather than
   relying on Reflex having imported them for something else on the page.
2. Backend port 8010 was already held by another local process → moved to **8011**.

---

## Phase 1 — The core loop ★

**Goal:** the product's reason to exist — click, buffer, history.

- [ ] `on_map_click` → `AppState.set_study_point(lat, lon)`.
- [ ] `services/buffers.py`: point → 1/2/5/10 km geometries, **disc and ring modes**
      (decision D2), returned as GeoJSON for display and `ee.Geometry` for analysis.
- [ ] Buffer outlines drawn on the map, labelled, with a marker at the study point.
- [ ] `services/mapbiomas_history.py`: the **single batched `reduceRegions`** across
      4 buffers × 40 bands ([06-ee-layers.md](06-ee-layers.md) §4), with the
      `tileScale`/`scale` retry ladder and `Provenance`.
- [ ] Fan-out on the same click: prefetch all 40 year tile URLs concurrently (§5b).
- [ ] Plotly **stacked column chart**, one column per year, official MapBiomas colours,
      one chart per buffer + a buffer selector.
- [ ] Result cache keyed on rounded coordinates; in-flight deduplication; stale-response
      cancellation when the user clicks again.
- [ ] Out-of-Brazil / all-water click detection with an honest message.

**Done when:** clicking anywhere in Brazil produces four 1985–2024 land-cover histories
in a few seconds, and clicking the same spot again is instant.

---

## Phase 2 — Seeing it on the map 🚧 **in progress**

**Goal:** the land cover behind the chart, and the ability to move through time.

- [x] MapBiomas raster layer with an opacity control.
- [x] **Year control** — slider over 1985–2024, instant because all 40 tile URLs are
      prefetched on startup (window first, then the rest).
- [x] **Swipe comparison** — two MapBiomas years on screen at once, split by a
      draggable vertical divider. See §"Swipe" below.
- [x] **Natural-vegetation change mask** — see §"Change mask" below.
- [ ] Buffer-clipped MapBiomas (currently full extent only).
- [ ] Interactive legend listing only the classes present in view, with areas;
      clicking a class isolates it.
- [ ] Chart ↔ map linkage: hovering a year in the chart previews it on the map.
- [ ] Play/pause step-through of the year series.

### Change mask — candidates for recovery projects

`services/change_mask.py`. Classifies every pixel between a baseline year and the
latest as **natural lost** (restoration candidate), **regrowth**, or **stable natural**.

The baseline defaults to **2008 because that is the Forest Code milestone**: native
vegetation cleared before 22 July 2008 can be regularised as *área consolidada*, while
clearing after it carries a restoration obligation. So "natural in 2008, not natural
today" approximates the legally-obligated restoration set. It is also the year of the
SPOT mosaic (Phase 4), which gives 5 m imagery to check a candidate by eye — not a
coincidence, since Google built that mosaic for the Forest Code programme.

⚠️ **Screening, not a legal finding.** MapBiomas is annual and 30 m; the Forest Code
operates on a date, on CAR parcels, with APP/Reserva Legal distinctions, small-holding
exemptions and authorised-clearing permits. The UI carries this caveat inline and must
keep doing so.

Measured at Machadinho d'Oeste, RO (10 km buffer, 2008→2024): 4 451 ha natural lost,
274 ha regrowth, 9 778 ha stable natural.

### Swipe — two years at once

The divider is dragged and the clip recomputed entirely in the browser; the split
position is a viewing preference with no analytical meaning, so the backend never learns
about it and there is no per-mouse-move round-trip.

**Two non-obvious things this cost:**

1. **`clip-path: inset(%)` does not work on a Leaflet layer.** A `.leaflet-layer`
   container has no intrinsic size — Leaflet leaves it 0×0 and positions tiles as
   absolutely-placed children outside it — so percentage insets resolve against a 0×0
   box and clip the layer away entirely. Both halves vanish while the tiles sit in the
   DOM fully loaded, which looks like a data problem. The fix is the legacy
   `clip: rect(...)` in **layer-pixel** coordinates via `containerPointToLayerPoint`,
   recomputed on every `move`/`zoom` — the approach `leaflet-side-by-side` uses.
2. **The divider must not swallow map clicks.** It lives inside the Leaflet container,
   so without `L.DomEvent.disableClickPropagation` every grab of the divider also drops
   a new study point underneath the cursor. Its grab area is 24 px wide around a 2 px
   visual line; 2 px is unusable with a mouse and impossible on touch.

Verified seamless: with both sides set to the same year, each half is **pixel-identical
(RMSE 0)** to the unclipped single layer.

**Done when:** a user can scrub 1985→2024 and watch the buffer repaint without stutter.

---

## Phase 3 — Vegetation age ★

**Goal:** how old is the forest and natural vegetation in each buffer? This is the
analytical core of the product — read [10-forest-age.md](10-forest-age.md) in full before
writing any of it.

- [ ] `config/mapbiomas.py`: natural-vegetation class groups (forest formations, natural
      non-forest, planted forest, anthropic, masked), **validated against the official
      Collection 10.1 legend** — not against Yvynation's convenience label table (**D6**).
- [ ] `services/hansen.py`: GFC tree cover / loss year / gain, ocean+`datamask` handling.
- [ ] `services/vegetation_age.py`:
      - [ ] **E1** — MapBiomas *Deforestation & Secondary Vegetation* v3, last regrowth
            year via `ImageCollection(...).max()`; year range clamped to 1987–2024.
      - [ ] **E2** — annual MapBiomas series establishment year, **with the ≥3-consecutive-
            year persistence rule** (a bare year-to-year `neq` will read flicker as regrowth).
      - [ ] **E3** — Hansen `lossyear` as an independent upper bound on age;
            `treecover2000` threshold user-configurable, default 30 %.
      - [ ] Fusion: most recent disturbance from any source wins; censored otherwise.
      - [ ] Confidence flag (high / medium / low) from inter-source agreement.
- [ ] Single fused `reduceRegions` producing the age-class histogram for all four buffers;
      the three estimator builds submitted concurrently.
- [ ] Fire qualifier from MapBiomas Fire c4 (`fire_frequency`, `year_last_fire`) attached
      to each age class — as a qualifier, **not** an age reset (**D7**).
- [ ] Charts: age-class distribution per buffer; forest formations and natural non-forest
      **visually separated, never pooled**.
- [ ] Headline stats: median age of dated vegetation, **censored share**, total natural
      area, confidence breakdown.
- [ ] Map layers: vegetation age (with a distinct flat colour for censored), establishment
      year, confidence, source disagreement.
- [ ] **Censoring surfaced in the UI**: the ≥40 y class labelled as *"no conversion observed
      since 1985"*, never as a numeric bin; no mean that folds censored pixels in at their
      floor (constraint **C5**).
- [ ] Internal-consistency test: natural area from the age product reconciles with the
      Phase 1 MapBiomas history for the same year.

**Done when:** clicking a point yields an age-class distribution per buffer whose censored
share is stated plainly, and the age map layer visibly distinguishes recent regrowth from
"older than the record".

**Not done when** it merely produces a number. If the censored share is not on screen next
to the summary, this phase is not finished.

---

## Phase 4 — Satellite context

**Goal:** imagery underneath the classification.

- [ ] Sentinel-2 median composite with Cloud Score+ masking (`cs ≥ 0.60`), user date
      window, true- and false-colour.
- [ ] Landsat 8/9 C02 L2 with scaling and `QA_PIXEL` masking; per-mission band aliases so
      L5/L7 can be added for the pre-2013 era.
- [ ] MODIS EVI: the layer *and* the 16-day time-series chart per buffer, with the 1 km
      noise caveat surfaced in the UI.
- [ ] **SPOT 2008** visual + analytic + derived NDVI — **gated on the licence
      prerequisite below**.

> ### ⚠️ Prerequisite, start it now
> `GOOGLE/BRAZIL_FOREST_2008/V1/*` requires accepting the *Brazil Forest Imagery Dataset
> 2008* licence agreement via Google's form, and the **service account** that runs the app
> must be the one granted access. This is a paperwork lead time, not a coding task —
> **submit it during Phase 0** so it is not what blocks Phase 4. Until it clears, the SPOT
> layers ship behind a feature flag that renders a licence explanation instead of an
> error.

**Done when:** every layer in [06-ee-layers.md](06-ee-layers.md) §3 draws correctly, or is
cleanly disabled with a reason.

---

## Phase 5 — IFN points

**Goal:** ground-truthed locations as first-class entry points.

- [ ] Run `scripts/fetch_ifn.py --all --build-catalog`; commit `data/ifn_points.csv`
      and `data/ifn_points.meta.json`. Re-check the size against the 2 MB guard.
- [ ] Decode the metadata PDFs — at minimum the `Relevo` codes and any `uso-do-solo`
      variables we intend to display. **Do not surface undecoded column codes in the UI.**
- [ ] `services/ifn_catalog.py` loads the CSV catalogue once at startup.
- [ ] Canvas circle-marker layer, coloured by *bioma*.
- [ ] Sidebar filters: **estado**, **bioma**, **status** (derived — see
      [05-ifn.md](05-ifn.md) §4), plus a text search on `ua`.
- [ ] Filtered list ↔ map share one collection; selecting in either highlights in both.
- [ ] Selecting a point runs the full Phase 1/2/3 analysis at its coordinates and shows the
      plot's own attributes alongside.
- [ ] "Derived status" explanation visible wherever the filter appears.
- [ ] **Age validation against IFN plots** — compare estimated age/class at IFN points
      against field-observed land use ([10-forest-age.md](10-forest-age.md) §7). This is
      the strongest validation available and a genuine research output in itself.

**Done when:** a user can filter to *Cerrado / Goiás / medido_completo*, click a point in
the list, and get its land-use history.

---

## Phase 6 — Export and provenance

Full specification in [11-exports.md](11-exports.md).

- [ ] **Grouped ZIP export**: `point.csv` plus one directory per buffer
      (`buffer_01km/`, `buffer_02km/`, `buffer_05km/`, `buffer_10km/`), each containing
      `landuse_history.csv`, `landuse_summary.csv`, `vegetation_age.csv` and — when
      computed — `evi_series.csv`.
- [ ] **Flat long-format CSV** alternative with a `scope` / `buffer_km` column, generated
      from the same DataFrame so the two forms cannot disagree.
- [ ] `geometry.geojson` — study point + all four buffer polygons.
- [ ] `provenance.json` + human-readable `README.txt` in every export, carrying dataset
      IDs, bands, scale, reducer, `pixel_area_basis`, the age-estimator parameters, and
      **`degraded: true`** whenever the retry ladder had to coarsen the query.
- [ ] **`censored_share_pct` mandatory** in every age export (constraint C5).
- [ ] **Chart export** — PNG / SVG / interactive HTML / CSV, per chart and "export all",
      with size, scale factor and background options. **Client-side via Plotly `toImage`**;
      no kaleido, matplotlib or headless Chrome on the server.
- [ ] Required attributions for every contributing dataset written into `README.txt`
      (constraint C4).
- [ ] A methodology / sources page (`pages/about.py`) listing every dataset, its ID,
      licence and required attribution.
- [ ] Attribution visible on-map for whichever layers are active.

**Done when:** a user can download one ZIP, hand it to a colleague, and that colleague can
tell exactly which datasets and parameters produced every number in it.

---

## Phase 7 — Polish and beyond

Ordered by expected value, not commitment:

- **PT/EN i18n** wired through from the start of Phase 1 (see
  [07-ui-ux.md](07-ui-ux.md)); this phase is where the corpus gets completed.
- **Custom geometry upload** (GeoJSON/KML/shapefile-zip) as an alternative to a point.
- **Land-cover transition matrices** between two chosen years (Sankey / heatmap).
- **IFN `uso-da-terra` per-subparcela comparison** against MapBiomas at the plot — the most
  scientifically interesting extension available, and the strongest argument for the app.
- **Multi-point comparison** — two or three study points side by side.
- **Batch mode**, reusing Yvynation's hard-won concurrency lessons rather than its code —
  together with **multi-point export** ([11-exports.md](11-exports.md) §6), which the
  single-point directory layout is already designed to extend.
- **Deployment** (Cloud Run, following Yvynation's `CLOUD_RUN_DEPLOYMENT.md`).

---

## Cross-cutting, from day one

These are not a phase; they are done continuously or they do not get done:

| Practice | Why |
|---|---|
| `Provenance` on every analysis result | Constraint C5; retrofitting it is miserable |
| Large files never committed | Constraint C3; git history is hard to clean |
| i18n keys instead of literal strings | Retrofitting i18n across a UI is a week of tedium |
| Every EE call wrapped in retry + timeout | Transient failures are normal |
| Licence/attribution recorded when a layer is added | Constraint C4 |
| Inferred values shown with their censoring/confidence | Constraint C5 — the age feature is unusable without it |
