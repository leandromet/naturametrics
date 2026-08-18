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
├─ raw/                   ← GITIGNORED — downloaded originals, byte-for-byte
│  └─ ifn/
│     ├─ unidades-amostrais-por-uf-ifn/
│     ├─ ifn-uso-do-solo-e-observacao-do-entorno_disp-set2025/
│     └─ _metadata/       ← the SFB metadata PDFs
└─ cache/                 ← GITIGNORED — intermediates, EE exports, scratch
```

## What goes where

| Artefact | Location | Committed |
|---|---|---|
| IFN CSV/XLSX per UF, as downloaded | `raw/ifn/<dataset-slug>/` | no |
| IFN metadata PDFs | `raw/ifn/_metadata/` | no |
| Deduplicated IFN point catalogue | `ifn_points.csv` + `ifn_points.meta.json` | **yes** |
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

## Regenerating

```bash
python scripts/fetch_ifn.py --all --build-catalog
```

Re-run when the Serviço Florestal Brasileiro publishes a new `disp-` version. The
application never downloads at runtime — it only reads the committed GeoJSON.

## Provenance

Everything under `raw/ifn/` comes from **`https://dados.florestal.gov.br`** (CKAN),
licensed **CC-BY** (*Creative Commons Atribuição*). Attribution: *Serviço Florestal
Brasileiro — Inventário Florestal Nacional*. `fetch_ifn.py` writes a `_manifest.json`
next to the downloads recording the source URL, resource id and fetch timestamp for each
file, so the raw tree stays traceable even though it is not versioned.
