# 06 — Earth Engine: layers, queries and the cost budget

## 1. Authentication

Ported verbatim from Yvynation's `utils/ee_service.py::initialize_earth_engine`, which
tries three sources in priority order and short-circuits on a module-level flag:

1. **Env-var service account** — `EE_PRIVATE_KEY` + `EE_SERVICE_ACCOUNT_EMAIL`
   (+ `EE_PRIVATE_KEY_ID`, `EE_CLIENT_ID`), assembled into a credentials dict. This is the
   Cloud Run path.
2. **Application Default Credentials** — `ee.Initialize(project=...)`. This is the local
   dev path; `~/.config/earthengine/credentials` already exists on this machine.
3. **Service-account JSON file** — `EE_SERVICE_ACCOUNT_JSON` pointing at a key file.

`GCP_PROJECT_ID` must be set (EE requires a project since the high-volume endpoint
migration). Yvynation defaults it to `ee-leandromet`.

## 1b. Tier and the concurrency budget

The project runs under the Earth Engine **Partner tier**:

| Resource | Allowance |
|---|---|
| Compute | **~360 000 000 EECU-seconds / month** |
| Simultaneous requests | **up to 60 000** |

**This is not a scarce resource for this application** and the design should say so
plainly. A single interactive session issuing a few hundred concurrent requests is
statistical noise against that ceiling. The engineering rule that follows:

> Optimise for **wall-clock latency**, never for call count. Batch when batching removes a
> *serial* round-trip; otherwise **fan out**.

**The real ceilings are local, not remote.** With 60 000 concurrent slots available, the
things that will actually throttle us are:

1. **Earth Engine's HTTP connection pool.** `ee.data` routes every Cloud API call through
   one shared `requests.Session` carrying urllib3's stock adapter, which caps at **10
   connections per host**. Past the cap urllib3 does not block — it opens a throwaway
   connection, pays a fresh TLS handshake, discards it, and logs *"Connection pool is
   full"* per call. The parallelism silently becomes handshake overhead. Yvynation solves
   this in `utils/ee_concurrency.py::tune_ee_connection_pool()`, which remounts an
   `HTTPAdapter` sized to the worker count + 4 headroom, called once after
   `ee.Initialize`. **Port it verbatim and call it on startup** — without it, every
   fan-out design in this document underperforms for a non-obvious reason.
2. **Thread count in our own process.** `getInfo()` is network-bound and releases the GIL,
   so threads are cheap here; Yvynation's partner profile allows `ee_max = 64` concurrent
   EE requests. That is a sane starting point for Naturametrics too, tunable by env var.
3. **Response size.** A single `getInfo()` result has a payload limit; batching too
   aggressively runs into it long before quota does (see §5).

> ⚠️ **Tier expiry.** Yvynation records the uplift as expiring **2027-02-15**. Verify
> whether that applies to the shared project before designing anything that *requires*
> Partner-level concurrency to be usable. The design should degrade to "slower but
> correct" if the tier lapses, not break. Whether Naturametrics should run under its own
> EE-registered project — for isolation and clean attribution rather than for quota — is
> tracked as **D5**.

## 2. Tile URLs, not map HTML

```python
map_id = image.getMapId(vis_params)
tile_url = map_id['tile_fetcher'].url_format   # → 'https://earthengine.googleapis.com/v1/.../tiles/{z}/{x}/{y}'
```

`services/tiles.py` memoises this on a stable cache key (Yvynation's `_TILE_CACHE`
pattern). The URL is handed to the browser and Leaflet fetches tiles directly from
Google — **the app server is not in the tile path**, which is why year-switching can be
instantaneous once warm.

Cache keys must encode everything that changes the pixels:
`mapbiomas:c10_1:1998`, `s2:median:2024-01-01:2024-03-31:truecolor:cs060`,
`spot2008:visual`, `modis:evi:2015-07-04`.

⚠️ EE tile URLs carry a signed component and **expire** (order of hours — exact TTL not
verified). The cache must store a timestamp and re-mint on expiry; a 401/403 from the
tile endpoint should trigger a silent refresh, not a broken layer.

## 3. The layer catalogue

| Layer | Source | Construction | Vis |
|---|---|---|---|
| **MapBiomas `<year>`** | Collection 10.1 image | `.select(f'classification_{year}')` | `min:0, max:62, palette: MAPBIOMAS_PALETTE` |
| **MapBiomas — buffer only** | same | `.clip(buffer_geom)` | same |
| **MapBiomas change** | same | `.select(yA).neq(.select(yB))`, self-masked | single colour |
| **Sentinel-2 true colour** | `COPERNICUS/S2_SR_HARMONIZED` | date filter → Cloud Score+ mask (`cs ≥ 0.60`) → `.median()` | `['B4','B3','B2'], 0–3000` |
| **Sentinel-2 false colour** | same | same | `['B8','B4','B3'], 0–3000` |
| **Landsat true colour** | `LANDSAT/LC09|LC08/C02/T1_L2` | scale `×0.0000275 − 0.2`, `QA_PIXEL` mask, `.median()` | `['SR_B4','SR_B3','SR_B2'], 0.0–0.3` |
| **DSV primary/secondary** | MapBiomas DSV v3 | `.select(f'classification_{year}')` | `min:0, max:7`, 8-entry discrete palette |
| **Hansen tree cover 2000** | GFC | `.select('treecover2000').selfMask()` | `0–100, ['black','green']` |
| **Hansen loss year** | GFC | `.select('lossyear')`, masked `> 0` | `0–24, ['yellow','red']` |
| **Hansen gain** | GFC | `.select('gain').eq(1).selfMask()` | single colour |
| **GLAD GLCLU `<year>`** | `projects/glad/GLCLU2020/v2/LCLUC_<year>` | ocean-masked with `projects/glad/OceanMask ≤ 1` | raw 0–255 or 11-stratum remap |
| **Vegetation age** | derived (doc 10) | fused year-image, `current_year − establishment` | sequential ramp + flat colour for censored |
| **Establishment year** | derived (doc 10) | fused year-image | viridis over 1985–2024 |
| **Age confidence** | derived (doc 10) | 3-class categorical | categorical |
| **Fire frequency** | MapBiomas Fire c4 | `fire_frequency_1985_2024` | `0–20`, warm ramp |
| **MODIS EVI** | `MODIS/061/MOD13Q1` | `.select('EVI').multiply(0.0001)` on the nearest 16-day composite | `-0.2–1.0`, MODIS NDVI palette |
| **SPOT 2008 visual** | `GOOGLE/BRAZIL_FOREST_2008/V1/VISUAL` | direct | `['R','G','B'], 0–255` |
| **SPOT 2008 analytic** | `GOOGLE/BRAZIL_FOREST_2008/V1/ANALYTIC` | direct | `['N','R','G']`, `min:[156,62,53]`, `max:[6408,2584,2211]`, `gamma:0.9` |
| **SPOT 2008 NDVI** | analytic | `.normalizedDifference(['N','R'])` | `-0.2–1.0`, vegetation palette |
| **IFN points** | local GeoJSON | not EE — a Leaflet vector layer | canvas circle markers |

Both SPOT layers are gated behind the licence flag (see
[04-data-sources.md](04-data-sources.md) §2).

## 4. The MapBiomas history query — the performance-critical path

### The naive version, which we do not write

```python
for buffer in buffers:            # 4
    for year in range(1985, 2025):  # 40
        img.select(f'classification_{year}').reduceRegion(...).getInfo()
```
**160 *sequential* round-trips.** The problem is not the 160 calls — under Partner tier we
could issue them all at once without noticing the cost. The problem is the `for` loop:
each `getInfo()` is a full request/response with EE compute (~1–3 s), and serialised that
is tens of seconds to minutes of the user staring at a spinner. Unusable for the core
interaction.

### The version we do write

MapBiomas Collection 10.1 is **one image with 40 bands**. `reduceRegion` with a
histogram reducer applied to a multi-band image returns **one entry per band**, in one
call. And `reduceRegions` maps that across a `FeatureCollection` of geometries.

```python
BANDS = [f'classification_{y}' for y in range(1985, 2025)]

buffers_fc = ee.FeatureCollection([
    ee.Feature(ee.Geometry.Point([lon, lat]).buffer(km * 1000), {'radius_km': km})
    for km in (1, 2, 5, 10)
])

result = (
    mapbiomas.select(BANDS)
             .reduceRegions(
                 collection=buffers_fc,
                 reducer=ee.Reducer.frequencyHistogram(),
                 scale=30,
                 tileScale=4,
             )
             .getInfo()
)
# → 4 features; each has 40 properties, one per band,
#   each a {class_code: pixel_count} dict.
```

**One round-trip for the entire 40-year × 4-buffer matrix** — because the query is
*naturally* one query, not because we are rationing calls.

Pixel counts convert to area with the 30 m nominal pixel: `area_ha = count × 0.09`
(Yvynation uses exactly this). For results that must survive scrutiny at high latitude
this is an approximation — the rigorous form multiplies by `ee.Image.pixelArea()` under a
grouped reducer. Brazil spans ±33° so the error is small but not zero; the grouped-reducer
variant is specified as **D3** in [09-open-decisions.md](09-open-decisions.md), and
whichever is used goes into `Provenance.pixel_area_basis`.

### Cost sanity check

The 10 km disc is ~314 km² → ~349 000 pixels at 30 m → ~14 M pixel-reads across 40 bands;
all four discs ~17.5 M. Trivial against a 360 M EECU-second monthly budget, and well
inside `maxPixels=1e10` — but heavy enough in a *single request* that `tileScale` matters.
Guard rails (these are about per-request limits, not quota):

- `maxPixels = 1e10`, `tileScale = 4` (raise to 8 on `Too many pixels`/OOM retry).
- Retry ladder on failure: `tileScale 4 → 8`, then `scale 30 → 60` for the 10 km buffer
  only, recording the degraded scale in `Provenance`. **Never silently change scale
  without recording it.**
- Hard timeout with a user-visible message; never leave the spinner running.

### Caching

Key on `(round(lat, 5), round(lon, 5), radii, collection_version)`. Repeated clicks on the
same spot — which happen constantly while adjusting layers — must not re-query. An
in-process LRU of ~256 entries is enough for v1.

## 4b. The vegetation-age query

Structurally the same trick as §4, applied three times and fused. Each estimator collapses
40-ish annual bands into a **single year-valued image** server-side
(`ee.ImageCollection([...]).max()`), the three are combined into one fused establishment
image, and then **one `reduceRegions`** produces the age-class histogram for all four
buffers at once.

The three estimator builds are independent, so they are submitted **concurrently** (§5b);
the fusion and the single reduction follow. Net wall-clock cost is roughly one round-trip.
Method, class definitions and the censoring rules are in
[10-forest-age.md](10-forest-age.md) — read that before implementing this.

## 5. MODIS EVI time series

Same batching philosophy, different shape. ~600 composites since 2000; the series is
needed per buffer.

```python
modis = (ee.ImageCollection('MODIS/061/MOD13Q1')
           .filterDate(start, end)
           .select('EVI'))

series = modis.map(lambda img: ee.Feature(None, {
    'date': img.date().format('YYYY-MM-dd'),
    'evi': img.multiply(0.0001).reduceRegion(
        ee.Reducer.mean(), buffer_geom, 250, maxPixels=1e9).get('EVI'),
})).getInfo()
```

One `getInfo()`, server-side `map`. ⚠️ For long windows this can approach EE's **response
size** limit (not a quota limit); when it does, chunk into 5-year windows and **issue the
chunks concurrently** on the EE executor — four parallel chunks cost the same wall-clock
as one. Note the 250 m pixel: a 1 km buffer holds only ~50 MODIS pixels, so **the 1 km EVI
series is noisy and must be labelled as such**; 5 km and 10 km are the meaningful ones.

## 5b. Fan-out and prefetching

Batching (§4) removes serial round-trips *within* one logical query. Everything that is
**not** one logical query should be issued **concurrently**. Port Yvynation's
`utils/ee_concurrency.py` primitives — `get_ee_executor()` (a sized `ThreadPoolExecutor`,
partner profile `ee_max = 64`) and `tune_ee_connection_pool()` — and use them everywhere.

Yvynation's module is sized for a *batch* pipeline and carries a lot we do not need
(territory lanes, kaleido/matplotlib render lanes, pool meters). Take the EE executor, the
connection-pool fix, the tier profiles and the env-var overrides; leave the rendering
machinery behind.

### What runs concurrently on a single map click

```
set_study_point(lat, lon)
   │
   ├── MapBiomas history, 4 buffers × 40 years ──▶ 1 reduceRegions call
   ├── Vegetation age: E1 / E2 / E3 estimators   ──▶ 3 concurrent builds, 1 fused reduceRegions
   ├── MapBiomas tile URLs for all 40 years    ──▶ 40 getMapId calls, fanned out
   ├── MODIS EVI series per buffer             ──▶ up to 4 (or 4 × N chunks), fanned out
   ├── Sentinel-2 composite for the current window ─▶ 1
   └── reverse geocode / municipality lookup   ──▶ 1 (non-EE)
```

Submitted together, the whole set completes in roughly the time of the **slowest single
call**, not their sum. Results stream into state as each future resolves, so the history
chart can render while imagery is still minting.

### Speculative prefetch

Under the old contributor-tier assumptions, minting 40 tile URLs when the user might look
at three of them would have been waste. Under Partner tier it is **the correct default**:

| Trigger | Prefetch |
|---|---|
| Point clicked | All 40 MapBiomas year tile URLs (makes the year slider instant) |
| Point clicked | Buffer-clipped MapBiomas for the currently active year |
| Year slider moved | ±3 years around the new position, if any are cold |
| IFN filter applied | Nothing — the catalogue is local |
| Satellite layer enabled | The composite for the current window only (date windows are user-chosen, so guessing is not useful) |

Prefetch work is submitted at **lower priority** than the foreground query — in practice,
submit the foreground futures first and let the executor queue absorb the rest.

### Discipline that still applies

Wide concurrency does not excuse carelessness:

- **Deduplicate in-flight work.** Two rapid clicks on nearby points must not double-issue;
  key the cache (§4) *before* submitting, and let a second caller await the first future.
- **Cancel superseded work.** If the user clicks a new point while the previous analysis is
  in flight, mark the old result stale and drop it on arrival — never let a late response
  overwrite newer state.
- **Bound the pool anyway.** 60 000 remote slots does not mean 60 000 local threads. The
  executor size is a memory and file-descriptor decision, not a quota one.
- **Retry with backoff.** Transient 5xx/429 still happen; `_ee_with_retry`-style wrapping
  belongs around every call.

## 6. Failure modes to handle explicitly

| Failure | Response |
|---|---|
| Click outside Brazil | MapBiomas has no data → empty histogram. Detect *before* querying, with a bbox/land test, and say so. |
| Click in the ocean | Same; the buffer may be entirely water. |
| SPOT asset not authorised | Layer disabled with a licence explanation, not an error toast. |
| No cloud-free S2 in window | Empty composite → tell the user to widen the date range. |
| EE quota exhausted / 429 | Backoff + a clear "Earth Engine is rate-limiting" message. |
| Tile URL expired | Silent re-mint (see §2). |
| Buffer crosses the antimeridian | Not possible in Brazil. Ignore. |
| Buffer has no natural vegetation at all | Age analysis returns empty, not zero. Say "no natural vegetation in this buffer", never "0 years". |
| DSV asset year clamp (starts 1987) | Requested 1985–86 silently outside range → clamp and record it in `Provenance`, as Yvynation does. |
| Hansen `datamask == 2` (water) | Excluded before any age fusion, or water reads as undisturbed forest. |
