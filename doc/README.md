# Naturametrics — Documentation Index

**Naturametrics** is a geospatial portal for **land-use history and landscape analysis**
anywhere in Brazil. You click a spot on the map (or pick a National Forest Inventory
sampling point) and get the full MapBiomas land-cover trajectory for concentric buffers
around it, plus satellite context imagery from Earth Engine.

It is a **sibling** of [Yvynation](../../../home/leandromb/google_eengine/yvynation), not a
fork of it: Yvynation stays focused on monitoring *protected and Indigenous territories*;
Naturametrics targets *general environmental study of any location*. Yvynation is the
reference for the technology stack (Reflex, Earth Engine access patterns, geometry
handling, visual language) — see [02-architecture.md](02-architecture.md) for what we
reuse and what we deliberately change.

## Read in this order

| # | Document | What it answers |
|---|---|---|
| 01 | [premises.md](01-premises.md) | Why this app exists, scope, non-goals, guiding constraints |
| 02 | [architecture.md](02-architecture.md) | Package layout, state model, the map-rendering decision |
| 03 | [roadmap.md](03-roadmap.md) | Phased delivery plan with acceptance criteria |
| 04 | [data-sources.md](04-data-sources.md) | Every external dataset, its ID, licence, size and caveats |
| 05 | [ifn.md](05-ifn.md) | National Forest Inventory: grid, schemas, the "status" problem |
| 06 | [ee-layers.md](06-ee-layers.md) | Earth Engine layer specs, vis params, the query-cost budget |
| 07 | [ui-ux.md](07-ui-ux.md) | Screens, interaction flows, the year/legend control |
| 08 | [dev-environment.md](08-dev-environment.md) | venv, env vars, ports, commands |
| 09 | [open-decisions.md](09-open-decisions.md) | **Decision record** — D1–D10, all accepted 2026-08-18, with the reasoning kept |
| 10 | [forest-age.md](10-forest-age.md) | Vegetation-age estimation from MapBiomas + Hansen — method, fusion, caveats |
| 11 | [exports.md](11-exports.md) | CSV/chart export layout, grouping per buffer, provenance |

## Language

Docs are written in **English**, matching the Yvynation reference docs, but Portuguese
domain terms are kept verbatim where they are the canonical names (*bioma*, *unidade
amostral*, *conglomerado*, *lote*, *uso do solo*). The **application UI is planned as
bilingual PT/EN** from the start — see [07-ui-ux.md](07-ui-ux.md).

## Status

Documentation phase; **D1–D10 accepted 2026-08-18** ([09](09-open-decisions.md)). No
application code written yet. `git log` is a single initial
commit; the repo currently holds only `LICENSE`, `.gitignore`, `.gitattributes`, this
`doc/` folder, `scripts/`, and the `data/` placeholder.
