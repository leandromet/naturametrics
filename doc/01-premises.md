# 01 — Premises

## 1. Why a separate application

Yvynation answers a narrow question well: *what is happening to this protected /
Indigenous territory and its surroundings?* Its whole model — territory registries
(FUNAI, conservation units), external-ring buffers around a **known polygon**, batch runs
over a list of territories, governance/policy reporting — is built around a
**pre-existing, curated boundary**.

Naturametrics answers a different question: *what is the land-use history and landscape
context of **this arbitrary place**?* The entry point is a **coordinate**, not a
registry entry. Bolting this onto Yvynation would mean two incompatible mental models in
one navigation tree, two meanings for "study area", and a settings surface that confuses
both audiences. Hence a separate app.

**What is shared is the engineering, not the product**: Earth Engine authentication,
tile-URL caching, geometry conversion helpers, the MapBiomas class/colour dictionaries,
the Reflex state-mixin structure and the general visual language are all carried over
from Yvynation (see [02-architecture.md](02-architecture.md)).

## 2. Scope — v1

The first shippable version does exactly this:

1. **Click anywhere on a map of Brazil** → a study point is created.
2. **Concentric buffers** of **1 km, 2 km, 5 km and 10 km** are generated around it.
3. For each buffer, a **MapBiomas land-cover history 1985–2024** is computed and shown as
   a **stacked column chart, one column per year**, coloured with the official MapBiomas
   palette.
4. The **land cover of those buffers can be displayed on the map**, with a **year control
   in the legend** so the user can step/scrub through the time series and watch the
   buffer repaint.
5. **Vegetation age** is estimated for each buffer by combining the MapBiomas
   *Deforestation & Secondary Vegetation* product, the annual MapBiomas series and
   **Hansen Global Forest Change**: how long has the forest and natural vegetation here
   been standing? Output is an **age-class distribution per buffer** plus an **age map
   layer**, always paired with the censored fraction and a confidence flag. Full method
   and its limits in [10-forest-age.md](10-forest-age.md).
6. **Satellite context layers** from Earth Engine can be toggled underneath: Sentinel-2,
   Landsat, MODIS EVI, Hansen/GLAD forest layers, and the **Google Brazil Forest 2008
   (SPOT) mosaic** in both its visual and analytic flavours.
7. **National Forest Inventory (IFN) sampling points** are a selectable layer — the full
   national grid, 17 479 usable conglomerados. It is filterable by *região*, *bioma*,
   *estado* and *município*, cascading, with the count and the framing answered from a
   precomputed local index rather than a query. Zoomed in past z8 the points become
   interactive: hovering one previews the land cover in its 10 km buffer, and clicking
   one makes it the study point at its own published coordinates, so the whole buffer
   analysis above applies to it. A **multiple-selection** switch changes what a click
   means: conglomerados accumulate into a set, the map draws every chosen buffer at once,
   and the chart shows the **sum** of their areas per radius and year. Overlapping buffers
   are counted once per conglomerado — the honest reading of a sum over sampling units,
   but not the area of the union, and the provenance line under the chart says so.
   *(The original plan listed a `status` filter. It is not offered: `status_derivado` is
   derived by us, not published by the SFB — see [05-ifn.md](05-ifn.md) §4 — and a filter
   is exactly the context where a derived field gets mistaken for an official one.)*
8. **Everything computed can be exported** — a grouped ZIP with `point.csv` plus one
   directory per buffer, a flat long-format CSV alternative, the geometries as GeoJSON,
   and every chart saveable as PNG / SVG / interactive HTML / CSV. Every export carries
   its provenance. See [11-exports.md](11-exports.md).

## 3. Explicit non-goals for v1

- **No territory registry.** No FUNAI / CNUC / CAR boundary browsing. That is Yvynation's
  and Terranalytics' job respectively.
- **No batch processing.** Yvynation's batch engine is large and hard-won; Naturametrics
  v1 is strictly interactive, one location at a time. Batch is a later phase and should
  reuse Yvynation's concurrency lessons rather than reinvent them.
- **No user accounts, no persistence of runs.** Results live in the session. Export is
  file-download only.
- **No property valuation, no fiscal modelling.** That is Terranalytics/`terra_web`.
- **No custom polygon upload** in v1. Point + buffers only. Upload is a natural phase-2
  addition and the geometry layer should be written so it does not preclude it.

## 4. Guiding constraints

### C1 — The map must not be rebuilt on interaction
Clicking the map is the *primary* gesture. Yvynation regenerates the whole Folium HTML
document whenever a layer changes, which discards the user's pan/zoom and costs a full
iframe reload. That is tolerable when layer changes are rare; it is unacceptable when the
core loop is click → look → click again, and fatal for a year slider. This drives the
central architectural decision in [02-architecture.md](02-architecture.md).

### C2 — Wall-clock latency is the budget, not Earth Engine quota
The project runs under an Earth Engine **Partner tier**: ~**360 million EECU-seconds per
month** and up to **60 000 simultaneous requests**. For an interactive, one-location-at-a-
time app that is effectively unlimited — **we should spend it freely.**

What we cannot spend freely is the user's time. The cost that matters is the **serial
round-trip**: each `getInfo()` is ~1–3 s of network + compute latency regardless of how
trivial the computation is. So the rule is not "make fewer calls" but:

> **Never do in sequence what can be done in parallel, and never make a round-trip whose
> result nobody is waiting for yet.**

Two consequences, both specified in [06-ee-layers.md](06-ee-layers.md):

- **Batch what is naturally one query.** "40 years × 4 buffers" is *one* `reduceRegions`
  call because MapBiomas ships 40 years as 40 bands of one image — not to save quota, but
  because one round-trip beats 160 sequential ones.
- **Fan out everything else.** Independent work — per-buffer queries that cannot be
  batched, MODIS series, tile-URL minting for every year in the legend, satellite
  composites — goes out **concurrently** on a wide thread pool. With 60 k simultaneous
  calls available, the limiting factors are our own HTTP connection pool and thread
  count, not Earth Engine.

**Speculative prefetching is encouraged.** Warming tile URLs for all 40 MapBiomas years
the moment a point is clicked costs us nothing meaningful and makes the year slider
instant. Under the old contributor-tier assumptions that would have been wasteful; under
Partner tier it is simply the right design.

### C3 — Large files never enter git
Raw IFN downloads, EE exports, tile caches and any GeoTIFF/XLSX bulk live under
`data/raw/` and `data/cache/`, which are gitignored. Only **small derived artefacts**
(the deduplicated IFN point table, lookup tables) are committed, and only if they stay
well under a megabyte. See [data/README.md](../data/README.md).

### C4 — Every dataset carries its licence
SPOT 2008 in particular is **not** freely usable without accepting a licence agreement
(see [04-data-sources.md](04-data-sources.md)). The app must surface attribution for
every layer it draws, and must degrade gracefully when an asset is not authorised for the
running service account.

### C5 — An inferred number carries its uncertainty or it does not ship
Vegetation age is *inferred* from a satellite record that starts in 1985. Most natural
vegetation in Brazil is older than that record, so its age is **right-censored**. Any
place the app shows an age, it must also show the censored share and the confidence
flag; a single "mean forest age" that quietly counts century-old forest as 40 years old
is the exact failure mode this constraint exists to prevent. See
[10-forest-age.md](10-forest-age.md) §5.

### C6 — Reproducibility over cleverness
Any number the app shows must be traceable to (dataset ID, band, year, geometry, scale,
reducer). The analysis layer returns these alongside the values, and exports include them.

## 5. Audience

Researchers, graduate students and environmental analysts who know their study area by
coordinates or by IFN plot ID, and who want the land-use trajectory of that place without
writing Earth Engine code. Secondary: teaching use, where the year-scrubbing map is the
point.
