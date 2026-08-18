# 02 — Architecture

## 1. Stack

Same spine as Yvynation, so knowledge transfers both ways:

| Concern | Choice |
|---|---|
| App framework | **Reflex** (Python-defined React frontend + FastAPI backend, one process) |
| Remote sensing | **Earth Engine Python API** (`earthengine-api`) |
| Map | **Leaflet**, driven directly (see §3) |
| Charts | **Plotly** (`plotly.graph_objects`), rendered through `rx.plotly` |
| Vector/geometry | **shapely** + **pyproj**; **geopandas** only in offline prep scripts |
| Tabular | **pandas** |
| Config | `.env` via `python-dotenv` |

Python **3.12** in a project-local `.venv`. Reflex pinned to the same minor as Yvynation
(`0.8.27`) so the component API matches the reference code — see
[08-dev-environment.md](08-dev-environment.md).

## 2. Package layout

Mirrors Yvynation's, which has proven navigable at ~100 kLOC:

```
naturametrics/
├─ rxconfig.py                  # Reflex config: app_name, ports, db_url
├─ naturametrics/
│  ├─ __init__.py
│  ├─ naturametrics.py          # app entry: rx.App(), add_page() calls
│  ├─ config/
│  │  ├─ __init__.py            # re-exports the public constants
│  │  ├─ datasets.py            # EE asset IDs, collections, date ranges
│  │  ├─ mapbiomas.py           # class labels + colour map + palette (ported)
│  │  └─ settings.py            # project id, scales, buffer radii, limits
│  ├─ state/
│  │  ├─ __init__.py            # AppState composed from the mixins below
│  │  ├─ _point.py              # clicked point, buffers, study-area lifecycle
│  │  ├─ _layers.py             # visible layers, tile URLs, active year
│  │  ├─ _analysis.py           # MapBiomas history job + results
│  │  ├─ _ifn.py                # IFN point catalogue, filters, selection
│  │  ├─ _export.py             # CSV/PNG/GeoJSON download handlers
│  │  └─ _ui.py                 # panels, tabs, language, toasts
│  ├─ components/
│  │  ├─ map/                   # the Leaflet component + its JS asset
│  │  ├─ legend.py              # MapBiomas legend + year control
│  │  ├─ charts.py              # stacked-column history, buffer comparison
│  │  ├─ layer_panel.py         # satellite/land-cover layer toggles
│  │  ├─ ifn_panel.py           # filters + point list
│  │  └─ layout.py              # shell, sidebar, header
│  ├─ pages/
│  │  ├─ index.py               # the map + analysis workspace (v1 is one page)
│  │  └─ about.py               # sources, licences, methodology
│  ├─ services/                 # ← "utils/" in Yvynation, renamed for intent
│  │  ├─ ee_client.py           # init + auth (ported from ee_service.py)
│  │  ├─ ee_concurrency.py     # sized EE thread pool + HTTP pool fix (ported)
│  │  ├─ tiles.py               # getMapId + tile-URL cache (ported ee_layers.py)
│  │  ├─ buffers.py             # point → buffer geometries
│  │  ├─ mapbiomas_history.py   # the batched multi-year reducer
│  │  ├─ hansen.py              # GFC tree cover / loss year / gain
│  │  ├─ vegetation_age.py      # the age estimator + fusion (see doc/10)
│  │  ├─ satellite.py           # S2 / Landsat / MODIS / SPOT composites
│  │  └─ ifn_catalog.py         # loads the derived IFN point table
│  ├─ api/
│  │  └─ routes.py              # extra FastAPI routes (downloads, healthz)
│  └─ assets/                   # static: naturametrics_map.js, css, logo
├─ scripts/                     # offline prep, not imported by the app
│  └─ fetch_ifn.py
├─ data/
│  ├─ raw/                      # gitignored — downloaded originals
│  ├─ cache/                    # gitignored — derived intermediates
│  ├─ ifn_points.csv            # committed — derived catalogue (D9)
│  └─ ifn_points.meta.json      # committed — its provenance
└─ doc/
```

Rationale for the two renames from Yvynation: `utils/` there has become a 500 kB grab-bag
where `ee_service.py`, `visualization.py` and `export_service.py` all live side by side;
calling it `services/` and keeping genuinely generic helpers out of it is a cheap
correction to make on day one. `state/` keeps the mixin pattern verbatim — it works.

## 3. The map: the one place we deliberately diverge

### How Yvynation does it
`utils/map_builder.py` builds a **complete Folium map** — basemaps, EE tile layers,
GeoJSON overlays, draw control — and returns `m._repr_html_()`. `AppState.map_html` is a
computed var; `components/map.py` drops it into `rx.html()`, which renders it in an
**iframe**. Any layer change bumps `geometry_version`, recomputing the HTML and
**reloading the iframe from scratch**. Reading state back out of the map (drawn features,
clicked territory) is done by `rx.call_script` reaching *into* the iframe's
`contentWindow` for globals the builder injected (`_yvyExportFeatures`, `_yvyTerritory`),
triggered by a hidden button.

That works, but it means: viewport lost on every change, ~1–3 s per toggle, a fragile
cross-frame bridge, and no way to build a responsive year slider.

### How Naturametrics does it
**One persistent Leaflet map, created once by our own JS, never destroyed.** Python never
generates map HTML.

```
Python (Reflex state)                    Browser
─────────────────────                    ───────
active layers, active year   ──props──▶  naturametrics_map.js
tile URL registry {key: url}             ├─ creates L.map once
                                         ├─ diffs incoming layer spec vs. what
                                         │  is on the map; adds/removes
                                         │  L.tileLayer accordingly
map click handler            ◀─event───  └─ map.on('click') → lat/lng
```

Concretely:

- A small **custom Reflex component** wraps a `<div>` and a companion JS module in
  `assets/`. It receives `layers: list[dict]` (each `{id, url, opacity, z, attribution}`)
  and `view: {center, zoom}` as props, and exposes `on_map_click` as a real Reflex event
  handler. Reflex supports this through `rx.Component` subclassing with
  `_get_custom_code()` / `add_imports()`, or — simplest first cut — a `rx.el.div` plus an
  `rx.script` module and `rx.call_script` for the outbound direction.
- **Tile URLs are computed in Python** by `services/tiles.py`, which is Yvynation's
  `_cached_get_map_id` pattern kept intact: `image.getMapId(vis)` →
  `map_id['tile_fetcher'].url_format`, memoised on a stable cache key. This is the part
  of Yvynation's EE work that is genuinely valuable and it ports unchanged.
- **Switching the MapBiomas year therefore costs one dictionary lookup** once the year's
  tile URL is warm — the JS swaps the layer, the viewport never moves. Pre-warming the
  tile URLs for the years around the current one is a cheap follow-up.

**Fallback:** if the custom component turns out to fight Reflex's rendering in practice,
the escape hatch is the Yvynation route (Folium → `rx.html`) with the year control
degraded to a discrete select instead of a slider. This is a real fallback, not a
theoretical one — it is a working reference implementation two directories away. The
decision is recorded in [09-open-decisions.md](09-open-decisions.md) as **D1**.

### Click → analysis flow

```
user clicks map
   └─▶ JS: map.on('click') → {lat, lng}
        └─▶ Reflex event: AppState.set_study_point(lat, lng)
             ├─ state/_point.py: builds 1/2/5/10 km buffers (ee.Geometry)
             ├─ pushes buffer outlines to the map as a GeoJSON overlay
             └─ state/_analysis.py: background event handler
                  └─ services/mapbiomas_history.py
                       └─ ONE batched reduceRegions call  ← see 06-ee-layers.md
                            └─ DataFrame → Plotly stacked columns
```

The analysis runs as a Reflex **background event handler** (`@rx.event(background=True)`)
so the UI stays responsive and can show progress; the pattern is already used by
Yvynation's analysis mixin.

The single batched call above is only the *foreground* half. Alongside it, the same click
fans out tile-URL minting for all 40 MapBiomas years, the MODIS series and any active
satellite composite onto a wide EE thread pool — the Partner tier makes that essentially
free, and it is what makes the year slider feel instant. See
[06-ee-layers.md](06-ee-layers.md) §5b.

## 4. State model

`AppState` is assembled from mixins, exactly as Yvynation does it
(`class AppState(PointMixin, LayerMixin, AnalysisMixin, IFNMixin, ExportMixin, UIMixin, rx.State)`).
Each mixin is `class XMixin(rx.State, mixin=True)` and owns a coherent slice:

| Mixin | Owns |
|---|---|
| `_point` | `study_lat`, `study_lon`, `buffer_radii_km`, `buffer_geojson`, `buffer_mode` |
| `_layers` | `visible_layers`, `active_year`, `layer_opacity`, `tile_urls`, `basemap` |
| `_analysis` | `history_df` (serialised), `age_df`, `analysis_running`, `analysis_error`, `provenance` |
| `_ifn` | `ifn_points`, `filter_uf`, `filter_bioma`, `filter_status`, `selected_ua` |
| `_export` | export selection (which buffers/analyses), download handlers |
| `_ui` | `sidebar_tab`, `language`, `legend_open`, toast queue |

**Rule carried over from Yvynation's experience:** never store `ee.Geometry` /
`ee.Image` objects in state vars — they are not serialisable. State holds GeoJSON dicts
and plain values; EE objects are reconstructed inside service functions. Yvynation
violates this in `buffer_utils.create_buffer_geometry_dict` (it stashes a live
`ee.Geometry` in a dict) and pays for it; we do not repeat that.

## 5. Analysis layer contract

Every analysis function returns a `(DataFrame, Provenance)` pair, where `Provenance` is a
small dataclass carrying `dataset_id`, `bands`, `scale_m`, `reducer`, `geometry_geojson`,
`pixel_area_basis` and `computed_at`. Constraint **C5** in
[01-premises.md](01-premises.md) is enforced here rather than by convention: the export
handlers refuse to write a file without one.

## 6. What is ported from Yvynation, verbatim or nearly

| Yvynation file | Becomes | Change |
|---|---|---|
| `utils/ee_service.py` (`initialize_earth_engine`) | `services/ee_client.py` | Verbatim; it already handles env-var SA, ADC and JSON-file auth in priority order |
| `utils/ee_layers.py` (`_cached_get_map_id`, `_TILE_CACHE`) | `services/tiles.py` | Keep the cache; drop the Folium-specific `add_*_layer` wrappers |
| `utils/ee_concurrency.py` (`get_ee_executor`, `tune_ee_connection_pool`, tier profiles) | `services/ee_concurrency.py` | **Take the EE half only.** The connection-pool fix is essential (urllib3 caps at 10 connections and silently degrades fan-out); leave the render lanes, territory lanes and pool meters behind |
| `config/config.py` (`MAPBIOMAS_LABELS`, `MAPBIOMAS_COLOR_MAP`, `MAPBIOMAS_PALETTE`) | `config/mapbiomas.py` | Verbatim, plus PT labels |
| `utils/hansen_analysis.py`, `utils/deforestation_timeline.py` | `services/hansen.py`, `services/vegetation_age.py` | **Reference, not copy.** Take the validated DSV class-code semantics and the `_reduce_stacked` batching idea; the timeline module is built around per-year area series, which is a different question from per-pixel age |
| `utils/buffer_utils.py` (GeoJSON ↔ `ee.Geometry`) | `services/buffers.py` | Keep converters; replace the ring-only buffer with disc/ring modes; drop the `ee.Geometry`-in-a-dict function |
| `state/` mixin composition | `state/` | Structure only |
| Layout/visual language | `components/layout.py` | Adapted, not copied |

**Not ported:** the batch engine, territory services, policy/political context modules,
export ZIP pipeline, kaleido rendering lane, i18n corpus (we start a fresh, small one).
