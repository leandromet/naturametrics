# 04 — Data Sources

Every dataset the app touches, with the exact identifier, what it costs us, and what its
licence demands. **Verification date: 2026-08-18.** Facts marked ⚠️ were not verified
against a primary source and must be confirmed before they are relied on in code.

---

## 1. MapBiomas — Brazil land use / land cover

The backbone of the whole product.

| Field | Value |
|---|---|
| EE asset | `projects/mapbiomas-public/assets/brazil/lulc/collection10_1/mapbiomas_brazil_collection10_1_coverage_v1` |
| Type | **`ee.Image`** — a single image, one band per year |
| Bands | `classification_1985` … `classification_2024` (40 bands) |
| Resolution | 30 m |
| Values | MapBiomas class codes (0–62, plus 146/435/466 in the label table) |
| Licence | CC-BY-SA, attribution: "MapBiomas Project – Collection 10.1" |

Older collections, kept for comparison work: collection 9
(`.../collection9/mapbiomas_collection90_integration_v1`) and collection 8
(`.../collection8/mapbiomas_collection80_integration_v1`).

**The single-image, one-band-per-year layout is the reason the batching trick in
[06-ee-layers.md](06-ee-layers.md) works.** All 40 years can be reduced in one call
because they are bands of one image, not elements of a collection.

Class labels and the official colour map are ported from Yvynation's
`config/config.py` (`MAPBIOMAS_LABELS`, `MAPBIOMAS_COLOR_MAP`, `MAPBIOMAS_PALETTE`);
`MAPBIOMAS_PALETTE` there is built as a dense 0–62 list with `#808080` filling the gaps,
which is exactly what `getMapId` needs. Portuguese labels must be added — Yvynation's
table is English-only.

---

## 2. Google Brazil Forest Imagery Dataset 2008 (SPOT)

Two sibling assets, both **`ee.Image`**, both derived from SPOT 2/4/5 acquisitions
between **2007-01-01 and 2009-11-26** (predominantly 2008). Coverage is ~68 % of Brazil
on average and ~93 % over priority deforestation regions — **the app must handle "no data
here" as a normal case, not an error.**

### 2a. Visual basemap
| Field | Value |
|---|---|
| Asset | `GOOGLE/BRAZIL_FOREST_2008/V1/VISUAL` |
| Bands | `R`, `G`, `B` (0–255), plus `date` (epoch seconds), `scale`, `satellite` (2/4/5), `coregistered` |
| Resolution | **5 m** |
| Vis | `{bands: ['R','G','B'], min: 0, max: 255}` |

### 2b. Analytic basemap
| Field | Value |
|---|---|
| Asset | `GOOGLE/BRAZIL_FOREST_2008/V1/ANALYTIC` |
| Bands | `G`, `R`, `N` (TOA reflectance ×10 000), plus `date`, `scale`, `satellite`, `coregistered` |
| Resolution | **10 m** |
| Vis (false colour N/R/G) | `min: [156, 62, 53]`, `max: [6408, 2584, 2211]`, `gamma: 0.9` |

The analytic bands allow an **NDVI for circa-2008** — `(N − R) / (N + R)` — which is
genuinely useful: it gives a pre-MapBiomas-modern-era vegetation reference at 10 m, far
finer than anything else in that period.

> ### ⚠️ Licence blocker
> These assets are **not open**. Access requires accepting the *"Brazil Forest Imagery
> Dataset 2008 license agreement"* via a Google form, and attribution is mandatory:
> *"Google LLC, Brazil Forest Imagery Dataset 2008 created from circa 2008 SPOT images"*.
> **Until the service account running Naturametrics has been granted access, these layers
> must be feature-flagged off and must fail closed with an explanatory message, never a
> stack trace.** This is a prerequisite task in [03-roadmap.md](03-roadmap.md), not a
> code detail.

Note: Yvynation's `config/config.py` already declares two SPOT asset paths
(`projects/google/brazil_forest_code/spot_bfc_rgb_mosaic_metadata_v03` and
`.../spot_bfc_ms_mosaic_v02`) but **never uses them**. Those look like the pre-publication
project paths; prefer the published catalogue IDs above, and treat the old paths as a
fallback only if the published ones are not visible to our account.

---

## 2b. MapBiomas — Deforestation & Secondary Vegetation ★

The authoritative basis for regrowth dating, and therefore for vegetation age.

| Field | Value |
|---|---|
| EE asset | `projects/mapbiomas-public/assets/brazil/lulc/collection10_1/mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3` |
| Type | `ee.Image` |
| Bands | `classification_1987` … `classification_2024` |
| Resolution | 30 m |
| Values | 0 Other · 1 Anthropic · **2 Primary veg** · **3 Secondary veg** · 4 Deforestation in primary *(event)* · **5 Regrowth** *(event)* · 6 Deforestation in secondary *(event)* · 7 Not applied |

Note the range starts at **1987**, not 1985 — year clamping is required. Classes 2 and 3
are *stable states* (roughly constant pixel counts over time); classes 4, 5 and 6 are
*annual events*. Confusing the two produces nonsense, and Yvynation's
`deforestation_timeline.py` carries an explicit comment about exactly that trap.

Why it matters: MapBiomas has already applied temporal consolidation to distinguish real
transitions from year-to-year classification flicker. Re-deriving regrowth from the raw
annual series means reinventing that filtering, badly. See
[10-forest-age.md](10-forest-age.md) §3.

## 2c. MapBiomas Fire — Collection 4

Used as a **qualifier** on vegetation age, not as an age input (§4 of
[10-forest-age.md](10-forest-age.md)).

| Product | Asset | Band |
|---|---|---|
| Fire frequency 1985–2024 | `projects/mapbiomas-public/assets/brazil/fire/collection4/mapbiomas_fire_collection4_fire_frequency_v1` | `fire_frequency_1985_2024` |
| Year of last fire | `.../mapbiomas_fire_collection4_year_last_fire_v1` | per-year `classification_{year}` bands |
| Annual burned scar size | `.../mapbiomas_fire_collection4_annual_burned_scar_size_range_v1` | `scar_area_ha_{year}`, classes 1–5 by size |

⚠️ Band naming in these assets is inconsistent between products; Yvynation resolves it at
runtime with a probing helper (`resolve_aux_band`) rather than trusting a fixed name. Port
that approach.

---

## 2d. Hansen — forest change

Two distinct product families, both already used by Yvynation, and they answer different
questions. **Keep them apart.**

### Global Forest Change (GFC) — the disturbance dater ★

| Field | Value |
|---|---|
| EE asset | `UMD/hansen/global_forest_change_2025_v1_13` (`ee.Image`) |
| Resolution | 30 m |
| `treecover2000` | Tree canopy cover in 2000, **0–100 %**. Vis: `min 0, max 100, palette ['black','green']` |
| `lossyear` | 0 = no loss; **1–24 → 2001–2024**. Vis: `min 0, max 24, palette ['yellow','red']` |
| `gain` | 0/1 tree-cover gain **2000–2012 only**, no year resolution |
| `datamask` | 0 no data · 1 land · 2 water |
| Licence | CC-BY 4.0, cite Hansen et al. (2013), *Science* 342:850–853 |

**What it is good for here:** an independent, globally consistent **stand-replacement
disturbance date**. That is the only role it plays in the age estimator.

**What it is not:** a definition of forest. `treecover2000` is canopy cover percentage,
blind to what the trees are — eucalyptus plantations, tree crops and dense cerrado all
pass a 30 % threshold, while genuinely natural open formations fail it. Never substitute
it for the MapBiomas natural-vegetation mask.

### GLAD GLCLU2020 — coarse land-cover strata

| Field | Value |
|---|---|
| Assets | `projects/glad/GLCLU2020/v2/LCLUC_{2000,2005,2010,2015,2020}`, plus `.../LCLUC` for change |
| Ocean mask | `projects/glad/OceanMask` — applied as `.lte(1)` |
| Values | 0–255 raw classes; Yvynation also ships an 11-stratum consolidation and a 256-entry palette |

5-yearly, so far too coarse in time to date establishment. Kept as a **map layer and
coarse cross-check only** — explicitly not part of the age estimator.

---

## 3. Sentinel-2

| Field | Value |
|---|---|
| Collection | `COPERNICUS/S2_SR_HARMONIZED` (surface reflectance, harmonised) |
| Resolution | 10 m (visible/NIR), 20 m (red-edge/SWIR) |
| Coverage | 2017-03 → present (L2A); L1C back to 2015-06 |
| Vis (true colour) | `bands: ['B4','B3','B2'], min: 0, max: 3000` |

**Cloud masking — use Cloud Score+, not the QA60 bitmask:**

| Field | Value |
|---|---|
| Collection | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` |
| Bands | `cs` (spectral distance from a clear reference), `cs_cdf` (CDF rank of that score) |
| Linking | Shares `system:index` with the S2 assets → join via `linkCollection()` |
| Threshold | **0.60** (documented useful range 0.50–0.65; higher removes thin cloud, haze, cirrus shadow) |

The app composites a **median over a user-chosen date window** after masking with
`cs >= 0.60`.

---

## 4. Landsat

| Field | Value |
|---|---|
| Collections | `LANDSAT/LC09/C02/T1_L2` (2021→), `LANDSAT/LC08/C02/T1_L2` (2013→) |
| Resolution | 30 m |
| Scaling | Collection-2 L2 optical bands need `× 0.0000275 − 0.2` to reach reflectance |
| Vis (true colour, post-scaling) | `bands: ['SR_B4','SR_B3','SR_B2'], min: 0.0, max: 0.3` |
| Cloud mask | `QA_PIXEL` bits — cloud (3), cloud shadow (4), dilated cloud (1), cirrus (2) |

Earlier missions (`LT05/C02/T1_L2`, `LE07/C02/T1_L2`) matter for the pre-2013 era, where
they are the only 30 m optical option overlapping the early MapBiomas years. Band names
differ (`SR_B3/B2/B1` for true colour) — a per-mission band-alias table belongs in
`config/datasets.py`.

---

## 5. MODIS EVI

| Field | Value |
|---|---|
| Collection | `MODIS/061/MOD13Q1` (Terra Vegetation Indices) |
| Cadence | 16-day composite |
| Resolution | 250 m |
| Bands | `EVI`, `NDVI` — **scale factor 0.0001**, valid range −2000…10000 |
| Coverage | 2000-02 → present |

Its role here is **temporal, not spatial**: at 250 m it is useless for a 1 km buffer as
imagery, but a 16-day EVI series 2000→present over a buffer is a strong companion to the
annual MapBiomas columns — it shows intra-annual dynamics (cropping cycles, drought,
burn recovery) that annual classification cannot.

`MODIS/061/MYD13Q1` (Aqua) can be interleaved for effective 8-day cadence — a later
refinement.

---

## 6. IFN — Inventário Florestal Nacional

Full treatment in [05-ifn.md](05-ifn.md). Summary of what we take:

| Dataset (CKAN slug) | Role | Format | Size |
|---|---|---|---|
| `unidades-amostrais-por-uf-ifn` | **Primary point geometry** — one row set per *unidade amostral*, with `lat_pc`/`lon_pc`, `bioma`, `uf`, `mun`, measurement `data` | CSV per UF (served under `.xlsx` names) | ~12–115 kB/UF |
| `ifn-uso-do-solo-e-observacao-do-entorno_disp-set2025` | Land use + surroundings observation per point (socio-environmental survey) | CSV per UF, `;`-delimited | ~50–200 kB/UF |
| `ifn-uso-da-terra-por-uf_disp-set2025` | Land-use class per *subparcela* — finest granularity | XLSX per UF | 140 kB–~1 MB/UF |

Portal: `https://dados.florestal.gov.br` — CKAN, so
`/api/3/action/package_show?id=<slug>` gives machine-readable resource lists. 60 datasets
published; ~19 are IFN. Licence **CC-BY** (*Creative Commons Atribuição*).

Methodology reference: `https://www.gov.br/florestal/pt-br/assuntos/ifn/metodologia`.
Portal: `https://snif.florestal.gov.br/pt-br/temas-florestais/ifn`.

---

## 6a. Own Earth Engine assets — IFN points and IBGE biomes

Three assets live in **our own** Earth Engine project (`ee-leandromet`): two uploaded
2026-08-19 from shapefiles, and one derived from them. Everything else this app reads is
public, so these are the only layers that break if the app is ever run under a different
`GCP_PROJECT_ID` without the assets being shared with it.

| Asset | Geometry | Features | Fields | Read by |
|---|---|---|---|---|
| `…/sfb_ifn_conglomerados_pontos` | MultiPoint | 17 495 | `co_pontos_`, `no_conglom`, `cd_mun`, `nm_mun`, `sigla_uf`, `nm_regiao`, `cod_mun_su` | the join script only |
| `…/sfb_ifn_conglomerados_pontos_bioma` ★ | MultiPoint | 17 479 | the above **plus** `bioma`, `dominio_fito`, `regiao_natural` | **the map** |
| `…/ibge_biome_domain_250k` | Polygon | 271 | `cd_bm`/`nm_bm`, `gl_dom`, `gm_dom`, `vg_dom`, `pd_dom`, `cd_dm_fito`/`nm_dm_fito`/`tp_dm_fito`, `cd_reg_nat`/`nm_reg_nat`/`tp_reg_nat` | the map, and the join |

All three under `projects/ee-leandromet/assets/`. The ★ asset is **derived** — written by
`scripts/join_ifn_biomes.py --export-asset`, not uploaded. Rebuild it whenever either
source asset is replaced.

Licences: SFB IFN **CC-BY** (as §6); IBGE biomes/domains **CC-BY** (IBGE open data).
Attribution strings are in `config/datasets.py` and are what the map's attribution
control shows.

### 6a.1 Known defects in the point asset

Verified against the asset, not assumed:

- **16 features have an empty `MultiPoint` geometry** — no coordinates at all. They are
  the same features that carry blank `sigla_uf`/`nm_mun`/`nm_regiao` (RJ and ES
  conglomerados). They cannot be drawn, joined or filtered. `scripts/join_ifn_biomes.py`
  drops them explicitly; without that they crash the join in `centroid()` with
  *"List is empty (index is 1)"*.
- **24 features have a blank UF** (the 16 above plus 8 with real geometry). Those 8 are
  on the map whenever no administrative filter is active, and invisible to the filters
  by construction. 5 of them also fall outside every biome polygon.
- **Usable total: 17 479.** That is the number the app counts and the number in the
  filter index.

### 6a.2 Why the biome is joined ahead of time, and not filtered spatially

The uploaded point asset carries **no biome column**, and the obvious fix — filter the
points with `filterBounds` against the biome outline — does not work:

| Biome | Points | `filterBounds` |
|---|---|---|
| Caatinga, Pampa, Pantanal | 2 367 / 523 / 374 | works |
| **Amazônia, Cerrado, Mata Atlântica** | 5 801 / 4 898 / 3 511 | **fails** — `Description length exceeds maximum` |

The three largest biomes have 1:250 000 outlines too long for Earth Engine's filter
machinery. It is not a request-size problem on our side (the serialised request is 1 369
characters either way) and it is unaffected by passing the `FeatureCollection` instead of
its `.geometry()`. Simplifying the outline would fix the request and quietly misassign
every point within the tolerance of a boundary — a silent correctness bug traded for a
size limit.

The symptom is worth recognising: the layer works for small biomes and silently draws
nothing for large ones, which reads as a zoom or density problem rather than a filter
failure.

So the intersection runs **once**, at full resolution, in
`scripts/join_ifn_biomes.py --export-asset`, and its result is stored as the ★ asset
above. In that asset `bioma` is a plain string property, so all four map filters are the
same `ee.Filter.eq`, and request size no longer depends on the size of the biome. The
same run also writes `data/ifn_filter_index.csv` (see `data/README.md`), so the asset and
the index the UI counts from are two outputs of one join and cannot disagree.

### 6a.3 How each is drawn

| Layer | Delivery | Why |
|---|---|---|
| IFN conglomerados | **Earth Engine tiles** — `FeatureCollection.style()` → `getMapId` | 17 479 points as GeoJSON is megabytes *per filter change*; as tiles it is a URL. All four filters are applied server-side, so each combination is its own cached tile URL. |
| IBGE biomes | **Browser vector layer**, fetched from the backend at `/_biomes.geojson` | The layer has to name itself on hover, and a tile is pixels. Simplified to 1.5 km and rounded to 2 dp: ~2.5 MB of JSON, **531 KiB gzipped**, fetched once and browser-cached. |

⚠️ **The served biome polygons are approximate to roughly a kilometre.** They are for
display and hover only, and nothing decides anything from them — the one place that
question is asked, which biome each IFN point sits in, was answered at full resolution by
the join above.

---

## 7. Basemaps

Plain XYZ tiles, no Earth Engine involved. **Esri World Imagery is the default** —
measured ~4x faster to first byte than the Google endpoints (67 ms vs 257 ms median).
Google Maps, Satellite, Hybrid and Terrain are offered alongside it and OSM.

| Key | Source |
|---|---|
| `google_maps` | `https://mt1.google.com/vt/lyrs=r&x={x}&y={y}&z={z}` |
| `google_satellite` | `…lyrs=s…` |
| `google_hybrid` | `…lyrs=y…` |
| `google_terrain` | `…lyrs=p…` |
| `esri_imagery` *(default)* | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` |
| `esri_topo` | `…/World_Topo_Map/…` |
| `osm` | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` |

Overridable with `NM_BASEMAP`.

⚠️ **The `mt1.google.com` endpoints are not a licensed public Google API.** They are
the same undocumented tile servers Yvynation uses; they are fast and they work, and
they are the chosen default. Before a public Cloud Run deployment (D10) this should
become a proper Google Maps Platform key, or fall back to Esri/OSM, which are
licensed for this use.

**Measured** (cache-disabled load, 1440×900, 2026-08-18): basemap tiles are **20
requests / 187 kB / ~0.13 s** — they are not a meaningful share of load time. The
cost on a hard reload is **4 MB across 34 JS module requests**, which is Vite dev
mode serving unbundled ESM and does not exist in a production build.

## 8. Storage footprint and git policy

| Artefact | Where | In git? |
|---|---|---|
| IFN raw CSV/XLSX (27 UF × 3 datasets) | `data/raw/ifn/` | **No** |
| IFN metadata PDFs | `data/raw/ifn/` | **No** |
| Derived deduplicated point catalogue | `data/ifn_points.csv` + `.meta.json` | **Yes** — CSV chosen over GeoJSON (~99 B/point vs ~281 B/point), **D9** |
| GeoJSON copy of the catalogue | `data/cache/ifn_points.geojson` | **No** — QGIS convenience only |
| MapBiomas class/colour tables + natural-class groups | `naturametrics/config/mapbiomas.py` | **Yes** (code) |
| Hansen palettes / stratum tables | `naturametrics/config/datasets.py` | **Yes** (code) |
| EE tile-URL cache | in-memory only | n/a |
| Any GeoTIFF / EE export | `data/cache/` | **No** |

Enforced by the `.gitignore` rules described in [data/README.md](../data/README.md).
