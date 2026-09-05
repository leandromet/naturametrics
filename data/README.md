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
├─ ifn_points_biome.csv   ← COMMITTED — one row per conglomerado, with its biome
├─ territorios.csv        ← COMMITTED — FUNAI + CNUC catalogue (name, UF, area, bbox)
├─ terras_indigenas.geojson.gz       ← COMMITTED — simplified FUNAI polygons
├─ unidades_conservacao.geojson.gz   ← COMMITTED — simplified CNUC polygons
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
| IFN per-point table with biome | `ifn_points_biome.csv` | **yes** |
| FUNAI/CNUC territory catalogue (search + bbox) | `territorios.csv` | **yes** |
| Simplified FUNAI / CNUC polygons served to the browser | `terras_indigenas.geojson.gz`, `unidades_conservacao.geojson.gz` | **yes** |
| FUNAI / CNUC GeoPackages, as downloaded | `raw/` (or outside the repo) | no |
| Simplified biome polygons served to the browser | `cache/ibge_biomes_250k.json.gz` | no |
| GeoJSON copy of the catalogue | `cache/ifn_points.geojson` | no |
| Any GeoTIFF, EE export, tile dump | `cache/` | no |
| Lookup tables, class dictionaries | `naturametrics/config/*.py` (code, not data) | **yes** |

## `territorios.csv` and the two territory overlays

Built by `scripts/fetch_territorios.py` from two GeoPackages — FUNAI's terras
indígenas (657) and the CNUC unidades de conservação (3 247). Together they are
**775 KiB of CSV plus 1.4 MB of pre-gzipped GeoJSON**, which is over the usual
bar for a committed artefact; three things carry it:

* **A deploy cannot rebuild them.** The Dockerfile builds from the git
  checkout, and reading a GeoPackage needs `geopandas`/`fiona`, which are not
  runtime dependencies. Leaving these ignored means the image ships without
  them and the territory search raises `FileNotFoundError` in production —
  exactly the failure `municipios.csv` was allowlisted to prevent.
* **The `.gz` files are committed in the form they are served.** `api/__init__
  .py` hands the bytes to the browser untouched, so there is no "compressed
  copy of a larger committed file" duplication here.
* **They are static.** FUNAI and CNUC publish new snapshots occasionally; when
  one lands, re-run the script and commit the diff.

The overlays are simplified to ~200 m and rounded to ~110 m. They are
**orientation, not determination** — they must never be used to decide whether
a point falls inside a terra indígena or a unidade de conservação, and nothing
in the app asks them to.

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

## `ifn_points_biome.csv` — why this one is committed too

The 17 479-row per-point table (1.2 MB) is what makes a conglomerado *reachable*. The
interactive layer answers "which conglomerados are in this viewport" from it on every pan
— a linear scan measured at **9 ms**, with no Earth Engine and no database in the path —
and the export enumerates it to decide what a selection covers. Serving that from Earth
Engine instead would put a 1–2 s round trip between the user and every map movement.

Same commit rationale as the index: a deploy cannot rebuild it, because the generator
needs Earth Engine credentials.

`cd_mun` is deliberately absent — it is blank wherever `nm_mun` is, nothing reads it, and
at 17 479 rows every column is real bytes in git.

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
python scripts/join_ifn_biomes.py --force             # both CSVs above
python scripts/join_ifn_biomes.py --export-asset      # the joined Earth Engine asset
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
