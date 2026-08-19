# `data/` — layout and git policy

## Rule

> **Raw downloads and bulk outputs never enter git. Only small derived artefacts do.**

This is constraint **C3** in [../doc/01-premises.md](../doc/01-premises.md). Git history is
painful to clean once a 50 MB XLSX is in it.

## Layout

```
data/
├─ README.md              ← committed (this file)
├─ .gitkeep
├─ ifn_points.csv         ← COMMITTED — derived, deduplicated IFN point catalogue
├─ ifn_points.meta.json   ← COMMITTED — its provenance (source, licence, generated_at)
├─ ifn_filter_index.csv   ← COMMITTED — counted (região, UF, município, bioma) groups
├─ ifn_points_biome.csv   ← GITIGNORED — the per-point table it is derived from
├─ raw/                   ← GITIGNORED — downloaded originals, byte-for-byte
│  └─ ifn/
│     ├─ unidades-amostrais-por-uf-ifn/
│     ├─ ifn-uso-do-solo-e-observacao-do-entorno_disp-set2025/
│     └─ _metadata/       ← the SFB metadata PDFs
└─ cache/                 ← GITIGNORED — intermediates, EE exports, scratch
   └─ ibge_biomes_250k.json.gz   ← built on first request, rebuilt if deleted
```

## What goes where

| Artefact | Location | Committed |
|---|---|---|
| IFN CSV/XLSX per UF, as downloaded | `raw/ifn/<dataset-slug>/` | no |
| IFN metadata PDFs | `raw/ifn/_metadata/` | no |
| Deduplicated IFN point catalogue | `ifn_points.csv` + `ifn_points.meta.json` | **yes** |
| IFN filter index (counts + bboxes per group) | `ifn_filter_index.csv` | **yes** |
| IFN per-point table with biome | `ifn_points_biome.csv` | no |
| Simplified biome polygons served to the browser | `cache/ibge_biomes_250k.json.gz` | no |
| GeoJSON copy of the catalogue | `cache/ifn_points.geojson` | no |
| Any GeoTIFF, EE export, tile dump | `cache/` | no |
| Lookup tables, class dictionaries | `naturametrics/config/*.py` (code, not data) | **yes** |

## Size guard

**Measured** on Acre + Goiás (1 074 unidades amostrais): CSV **106 kB**, GeoJSON **301 kB**
— GeoJSON repeats its keys per feature and runs ~2.9× larger. Extrapolated to 27 UFs at
10 000–15 000 points: **CSV ~1.1–1.5 MB**, GeoJSON ~3–4 MB.

**Decision D9 (accepted): the CSV is the committed artefact**, at 5 dp coordinates (~1 m,
far finer than a 20 km grid needs). The GeoJSON is still generated, into `cache/`, because
it drops straight into QGIS. Re-measure once all 27 UFs are downloaded — the extrapolation
is from two states and Goiás is unusually dense.

Check before committing:

```bash
du -h data/ifn_points.csv
git check-ignore -v data/raw/ifn/AC.csv   # should report a match
```

## `ifn_filter_index.csv` — why this one is committed

The map filters the IFN grid by região, estado, município and bioma. Everything the UI
needs to *drive* those filters — which options exist under the current choice, how many
conglomerados a combination selects, and the extent to frame it at — is answered by the
distinct (região, UF, município, bioma) groups, each with a count and a bounding box.

That is **4 513 rows, 326 KiB**, and it makes every filter interaction a dictionary
lookup instead of an Earth Engine round trip. It is committed because it has to be
present *before* the first request and a deploy has no way to build it: the generator
needs Earth Engine credentials and ~20 s.

The 17 479-row per-point table it is derived from (`ifn_points_biome.csv`, 1.3 MB) is
only useful once individual conglomerados become selectable, so it stays out of git and
is written on demand with `--full`.

| Column | Meaning |
|---|---|
| `regiao`, `uf`, `municipio` | from the SFB asset; empty for the handful of points with no administrative attributes |
| `bioma` | resolved by intersection with the IBGE polygons; empty for the 5 points outside every polygon |
| `pontos` | conglomerados in this group |
| `lon_min`, `lat_min`, `lon_max`, `lat_max` | their bounding box, 4 dp (~11 m) |

Any filter combination is answered by summing the matching groups and unioning their
boxes — which is exact, because the four columns are the group key.

## Regenerating

```bash
python scripts/fetch_ifn.py --all --build-catalog     # the point catalogue
python scripts/join_ifn_biomes.py --force             # the filter index
python scripts/join_ifn_biomes.py --force --full      # ...and the per-point table
```

Re-run `fetch_ifn.py` when the Serviço Florestal Brasileiro publishes a new `disp-`
version, and `join_ifn_biomes.py` whenever either Earth Engine asset is replaced. The
application never downloads at runtime — it only reads the committed files.

## Provenance

Everything under `raw/ifn/` comes from **`https://dados.florestal.gov.br`** (CKAN),
licensed **CC-BY** (*Creative Commons Atribuição*). Attribution: *Serviço Florestal
Brasileiro — Inventário Florestal Nacional*. `fetch_ifn.py` writes a `_manifest.json`
next to the downloads recording the source URL, resource id and fetch timestamp for each
file, so the raw tree stays traceable even though it is not versioned.
