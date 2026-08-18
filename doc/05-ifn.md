# 05 — Inventário Florestal Nacional (IFN)

## 1. What the IFN is

A federal field survey run by the **Serviço Florestal Brasileiro (SFB)**, sampling
Brazil's vegetation on a systematic national grid. For Naturametrics it provides
something valuable and unusual: **a set of real, ground-truthed locations distributed
across every biome**, each with a known identity, that a user can select and then analyse
with exactly the same buffer machinery as an arbitrary map click.

## 2. Sampling design (from the SFB methodology page)

- **Grid:** points **equidistant at 20 km** — a 20 km × 20 km national lattice. (Derived
  from 1° latitude ≈ 110 km, so 20 km ≈ 0.18°.) Densified variants exist at **10 km**
  (*grade 10*) and **5 km** (*grade 5*) for specific ecosystems and conservation areas.
- **Conglomerado:** at each grid point sits a sampling unit shaped like a **"Cruz de
  Malta"** (Maltese cross) — four rectangular subunits laid out perpendicularly on the
  cardinal directions.
- **Subunit size by biome:** 1 000 m² (20 m × 50 m) in Mata Atlântica, Cerrado, Caatinga,
  Pantanal and Pampa; **2 000 m² (20 m × 100 m) in Amazônia**. Each subunit is divided
  into 10 m × 10 m *subparcelas*.
- **Revisit:** proposed **five-year cycles**.

**Implication for the UI:** the whole conglomerado spans roughly a 200 m footprint. At
map scale it is a **point**, and the 1 km buffer already contains it entirely. So the
IFN point is a *location selector*, and the analysis it triggers is landscape-scale
context around a plot — which is precisely the intended reading.

## 3. The datasets we ingest

Portal: **`https://dados.florestal.gov.br`** (CKAN). Machine-readable listing:

```bash
curl -s "https://dados.florestal.gov.br/api/3/action/package_show?id=<slug>"
```

Each IFN dataset is published as **27 files, one per UF**, plus a metadata PDF.

### 3a. `unidades-amostrais-por-uf-ifn` — the geometry source ★

*"IFN - Dados Biofísicos - Unidades amostrais por UF_disp-mai2024"*

This is the primary table: it is the only one that reliably carries coordinates in a
clean form. **Resources are named `.xlsx` in CKAN but the download URLs end in `.csv` and
the payload is genuinely CSV** — a portal metadata error to be aware of.

- Encoding **UTF-8 with BOM** → read with `encoding='utf-8-sig'`
- Delimiter **`,`**, values quoted
- Decimal separator **`.`**

Columns (verified against Acre, 334 rows / 198 unique UAs):

```
bioma, uf, mun, lon_pc, lat_pc, ua, data, obs_gerais, outras_obs,
Relevo, Exp_terreno, Presen_erosao, Tipo_erosao, coleta_solo, impedimento,
metodo_coleta_solo, coleta_amostra_granel, horizonte_granel,
coleta_amostra_indefor, horizonte_indefor
```

| Column | Meaning | Example |
|---|---|---|
| `ua` | Sampling-unit identifier, `<UF>_<n>` | `AC_108` |
| `lat_pc` / `lon_pc` | Coordinates of the *ponto central* (WGS84) | `-8.45994099719817`, `-70.9203171819201` |
| `bioma` | Biome | `Amazônia` |
| `uf` | State code | `AC` |
| `mun` | Municipality | `Tarauacá` |
| `data` | Field measurement datetime | `2018/10/19 00:00:00` |
| `Relevo` | Relief code | `P`/`S`/`O`/`M` ⚠️ codes to be decoded from the metadata PDF |
| `impedimento` | Access impediment, `NA` when none | `Área alagada` |

**Rows repeat per UA** (soil sampling records — Acre has 334 rows over 198 UAs), so the
catalogue build must **deduplicate on `ua`**, keeping first non-null coordinates and the
earliest `data`.

### 3b. `ifn-uso-do-solo-e-observacao-do-entorno_disp-set2025` — land use & surroundings

*"IFN - Dados Socioambientais - Uso do solo e observação do entorno"*, released Sept 2025,
CC-BY.

- Encoding **UTF-8 with BOM**
- Delimiter **`;`**
- Decimal separator **`,`** ← different from 3a; `-8,460000` must be parsed accordingly
- Coordinates are **rounded to 6 dp but visibly truncated** (`-8,460000` vs the precise
  `-8.45994…` in 3a) → **never join on coordinates; join on `ua`.**

Columns (Acre, 594 rows / 209 unique UAs):

```
lote, ua, estado, bioma, municipio, lat_pc, long_pc, ids, tfp, efp, ufpl, aipf,
psmf, dnap, dnapn, dnaps1, dnaps2, apcf, tbp, nbr, pqbu, ubdc, otb, qeb, asub,
eag, eagf, saf, silvo, espf, ean, cpfl, pexo, pecot, eecot, cse, cde, inc, aes,
vue, pes, cos, coa, prsd, cas, conf, mpt, eap, deu, pen, mczu, mzuc, mcc, crie, gril
```

`lote` (e.g. `AC-01`) groups UAs into field campaign lots. `ids` appears to be a
respondent/interview index — multiple rows per UA. The short codes are questionnaire
variables and **must be decoded from `Metadados_IFN_Uso-solo-e-Obs-entorno_disp-set2025.pdf`**
before any of them is surfaced in the UI. `NA` is the null token throughout.

### 3c. `ifn-uso-da-terra-por-uf_disp-set2025` — land use per subparcela

*"classes de uso da terra em cada subparcela de cada subunidade da unidade amostral"* —
XLSX per UF, up to ~1 MB each. The finest-grained IFN product. **Phase 3**: it enables a
genuine field-vs-MapBiomas comparison at the plot, which is the most scientifically
interesting thing this app could do. Not needed for v1.

## 4. The "status" filter — an unsolved definition ⚠️

The user requirement is to filter points by **estado, bioma and status**. *Estado* and
*bioma* are direct columns. **Status is not a published field.** Neither the methodology
page nor the SNIF IFN page defines point-status categories, and no ingested CSV carries a
status column. This was checked, not assumed.

Two honest options:

### Option A — derive status from dataset membership (recommended for v1)

The published tables only contain points that were *actually surveyed*, and different
surveys cover different point sets. Acre: **198** UAs in the biophysical table, **209** in
the socio-environmental one — so membership genuinely differs and carries information.

| Derived status | Definition |
|---|---|
| `medido_completo` | Present in **both** `unidades-amostrais` and `uso-do-solo` |
| `medido_biofisico` | Only in `unidades-amostrais` (field plot measured, no survey) |
| `socioambiental` | Only in `uso-do-solo` (survey done, no biophysical record published) |
| `com_impedimento` | Any record with `impedimento != 'NA'` — flag, not a state |

This is defensible, computable today, and useful. It must be **labelled in the UI as
derived**, with the derivation shown in the tooltip and in `about.py` — presenting a
derived flag as if it were official IFN status would be the wrong kind of confident.

### Option B — obtain the official grid and status

Would require either the theoretical 20 km lattice (generatable: it is a regular grid, but
the exact origin and projection must match SFB's, which is not published) or a status
table from the SNIF interactive panels / a direct request to SFB. **Tracked as an open
item — see D4 in [09-open-decisions.md](09-open-decisions.md).** Until it resolves,
Option A ships with honest labelling.

## 5. Ingestion pipeline

`scripts/fetch_ifn.py` (already written — see `--help`) does:

```
CKAN package_show ──▶ per-UF resource URLs ──▶ download to data/raw/ifn/<dataset>/
                                                        │
                                                        ▼
                                          parse (per-dataset dialect)
                                                        │
                                     dedupe on `ua`, validate coords in Brazil bbox
                                                        │
                                          derive status (Option A)
                                                        │
                                        ▼                              ▼
                          data/ifn_points.csv  (+ .meta.json)   data/cache/ifn_points.geojson
                               COMMITTED, ~99 B/point                (QGIS working copy)
```

Run it manually and re-run when SFB publishes a new *disp-* version. It is **not** invoked
by the app at runtime; the app only reads the committed CSV via
`services/ifn_catalog.py`.

Expected scale: Acre has ~200 UAs and is a small state; a national total in the **low
thousands to ~10 000** points is the working assumption. At that size the catalogue loads
into memory once and filters client-side without a database.

## 6. Map rendering of the points

Thousands of markers will not render acceptably as individual Leaflet markers. Plan:

- **Canvas-rendered circle markers** (`L.circleMarker` with `preferCanvas: true`) — handles
  ~10 k points comfortably; **first choice**.
- Colour by `bioma`, size fixed, stroke on selection.
- Below a zoom threshold, optionally cluster; evaluate only if canvas rendering proves
  insufficient.
- Selection: click a marker → the same `set_study_point` path as a bare map click, plus
  `selected_ua` set so the panel can show the plot's attributes.
- The filtered list in the sidebar and the map layer read the **same** filtered
  collection, so the two views can never disagree.
