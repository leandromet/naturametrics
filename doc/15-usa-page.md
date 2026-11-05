# The USA page (`/usa`, lower 48)

A sibling of the Canada page, forked from `naturametrics/canada/` into `naturametrics/usa/` (2026-11-04). Own state root
(`USState`), services, components and translations; it shares the Earth Engine client, buffers, tile cache, ODS writer
and Leaflet component with the other pages.

## What it uses

| Panel | Source | Notes |
|---|---|---|
| Land-cover history | USGS **Annual NLCD** (Collection 1 v2), `projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER`, band `b1`, **1985–2025**, 30 m | National from the first year: no "starts late" or "stops at 58°N" caveat (unlike the Canada page's ACI). One `reduceRegions` for years × buffers, as elsewhere. |
| Forest change | Hansen GFC (global) | Unchanged from the Canada page. |
| Imagery | Landsat annual composites (global) | Unchanged. |
| Species | GBIF, `country=US`, 50 states + DC as GADM level-1 gids | gids checked live 2026-11-04. |
| Search | Nominatim (`countrycodes=us`) + ZIP via its structured postcode search | `services/address.py` is a shared file and is not edited for one country. |

## Extent

The lower 48, **Alaska** (east of 170°W) and **Hawaii**. A box per region (`REGION_BOXES`) rejects most clicks; **LSIB**
settles the points inside the boxes that are in Canada or Mexico (cached by 0.01° cell). Annual NLCD is conterminous only:
Alaska gets its three snapshot years (2001, 2011, 2016; `USGS/NLCD_RELEASES/2016_REL`), Hawaii has **no** NLCD land cover
(its images carry only `percent_tree_cover`), so that panel says so while every other panel answers. Puerto Rico and the
other territories are out.

## The American equivalents of the Canada page's stand age (and more)

The US has no measured stand-age raster in Earth Engine, so the page offers what the same question needs, from public
USFS/USGS products (all verified in Earth Engine 2026-11-04; the 2024-10 LCMS and 2023-9 TCC versions are deprecated, the
2025 ones are used):

| Panel | Source | What it answers |
|---|---|---|
| Disturbance history | **LCMS** v2025-11, `Change`, 1985–2025, CONUS/AK/HI | What changed each year and why: wildfire, tree removal, insects and drought, wind, regrowth |
| Time since disturbance | **derived from LCMS** | Tree pixels today, by years since the last tree-removing disturbance, **censored at 1985** (the last bar is "none since 1985", never an age) |
| Fire (MTBS) | **MTBS** annual burn severity mosaics | Burned area by year and severity; only fires ≥ 1 000 acres (west) / 500 (east) |
| Tree canopy | **NLCD Tree Canopy Cover** v2025-6 | Mean canopy % per buffer, 1985–2025 |

Map layers: tree canopy (year), last disturbance (LCMS) and MTBS severity, besides NLCD, Hansen and Landsat. The export
workbook has a sheet per panel. LCMS books a late-year fire in the following year (Camp Fire: MTBS 2018, LCMS 2019).

## Walkthrough

`/walkthrough/usa` — Paradise, California (Camp Fire, Nov 2018): `reportagem/naturametrics_us.{en.html,js}`, numbers from
`usa/services/demonstracao.py` (stored snapshot `data/demonstracao/naturametrics_us.json`, regenerate with
`python scripts/build_demonstracao.py us`). `tests/test_demonstracao_us.py` checks the fire shows up in every product.

## Not here

* **No measured stand age** (see above) and **no fire-frequency panel from MODIS**, same as the Canada page.
* **Suite links** (`suite_links.py`, shared) now know `usa`: clima → `?region=us`, yvynation and naturametrics → `/usa`;
  Camposcope has no USA page (no public national parcel service), so its link goes to its home.
* GBIF record types are ordered by their count for `country=US` (checked live 2026-11-04).

## Layer / cache ids

`us:nlcd:<year>` (`us:nlcd:ak:<year>` for Alaska), `us:tcc:<region>:<year>`, `us:lcms_loss:<region>`, `us:mtbs:<region>`,
`us:hansen_tc:<t>`, `us:hansen_change:<y>:<t>`, `us:landsat:<key>:<year>` — distinct from Canada's `ca:` ids because the tile
cache is shared.
