# 11 — Exports

Everything the app computes must leave the app. The rule from constraint **C6**
([01-premises.md](01-premises.md)) applies to every file written here:

> **No export without provenance.** A CSV that does not say which dataset, which bands,
> which geometry, which scale and which reducer produced it is not reusable, and
> six months later nobody — including its author — can defend the numbers in it.

---

## 1. Shape of a data export

**One ODS file per download, with a tab per table.** Not a ZIP of CSVs, and not a
directory tree — those were the original design here, and they were wrong for this
data. A spreadsheet is already a compressed container, it opens on a double-click, and
it keeps the metadata *attached* to the numbers instead of in a sibling file that gets
separated from them the first time someone forwards one sheet to a colleague.

The first tab of every export is `metadados`. There is no code path in
`services/exports.py` that writes a sheet of numbers without one — the workbook builders
take the `Provenance` records as required arguments.

### 1a. The study point

`naturametrics_ponto_<id>_<timestamp>.ods`

| Tab | Contents |
|---|---|
| `metadados` | Scope, coordinates, point origin (map click or conglomerado), buffer radii and mode, a provenance block per Earth Engine query, the citation, and the required attributions |
| `ponto_pixel` | The point's own 30 m pixel: `year, class_id, class_pt, class_en`, 40 rows |
| `buffer_01km` … `buffer_10km` | One tab per radius: `year, class_id, class_pt, class_en, pixels, area_ha, area_pct` |
| `resumo_por_classe` | Per buffer per class: first-year area, last-year area, net change in ha and % |
| `ponto_idade` | The point's own pixel, DSV estimator (doc/10-forest-age.md E1): `year, age, censored, class_id, class_pt`, 1987–2024 |
| `idade_01km` … `idade_10km` | One tab per radius: `age, bin, censored, pixels, area_ha` — at most CENSORED_AGE rows, since the histogram is over an age counter with a hard ceiling |
| `mudanca_2008_2024` | One row per radius: `radius_km, perda_ha, regeneracao_ha, estavel_ha` (services.change_mask, Forest Code baseline) |
| `classes_mapbiomas` | The code → name → colour dictionary, so no other tab is a column of bare integers |

Nothing is recomputed at export time. The land-cover and pixel tabs are the frame already
driving the chart, so the file and the screen cannot disagree. The idade/mudança tabs are
fetched in the same background run as the chart (state/_analysis.py `run_analysis`) but
trail it by a couple of seconds; a download requested while that fetch is still in flight
waits for it (bounded at 20 s) rather than shipping empty tabs with only a note in
`metadados` — a real race hit during development, not a hypothetical one. Measured: ~46 KiB
and 0.04 s for the original two tables; idade/mudança add a further ~2 KiB.

### 1b. A conglomerado selection

`naturametrics_conglomerados_<timestamp>.ods`

A selection is named in one of two ways, and everything downstream is identical:

* **by the four map filters** (região / bioma / estado / município), so "what will I get"
  is answered by looking at the sidebar; or
* **by hand** — the conglomerados clicked in multiple-selection mode. The panel offers
  this only when that selection is non-empty, and it is an explicit choice rather than an
  inference, so a few points left selected can never silently redefine a filter export.

Either way the file is **point by point**: one row per conglomerado, never the aggregate.
The sum shown in the chart is a reading of the data, not a shape for it — anyone can sum
a column, and nobody can recover the parts from a total. The panel offers three checkboxes
("pontos", "pixel", "buffers"), the third of which now writes five kinds of tab, because
they have very different costs:

| Tab | Contents | Cost |
|---|---|---|
| `conglomerados` | One row per point: id, região, UF, município, bioma, coordinates | free — read from `data/ifn_points_biome.csv` |
| `pixel_por_ano` | One row per conglomerado, one column per year, holding that pixel's class | **uncapped** — one streamed Earth Engine download; measured 17 479 points × 40 years = 2.3 MB in 1.9 s |
| `buffer_01km` … `buffer_10km` | one tab **per radius**: `conglomerado, uf, municipio, bioma, year, class_id, class_pt, class_en, pixels, area_ha, area_pct` | part of the buffer fan-out — **capped**, see §1c |
| `idade_01km` … `idade_10km` | one tab **per radius**: `conglomerado, uf, municipio, bioma, age, bin, censored, pixels, area_ha` (doc/10-forest-age.md E1) | part of the buffer fan-out — same cap |
| `mudanca_2008_2024` | one tab, all radii: `conglomerado, uf, municipio, bioma, radius_km, perda_ha, regeneracao_ha, estavel_ha` | part of the buffer fan-out — same cap |
| `classes_mapbiomas` | As above | free |

The three buffer-fan-out tables are one checkbox, not three: `services.exports`'s
`selection_age_frame` and `selection_change_frame` run as two further fan-out passes over
the same conglomerado list, sequentially after the land-cover pass
(`state/_export.py download_selection`). Combined pooled throughput measured 0.171 s per
conglomerado for age+change alone at 200 points; `EXPORT_SECONDS_PER_POINT` (settings.py) is
set from the sum of that and the land-cover pass, ~0.18 s, so the "≈ X min" estimate covers
all three passes, not just the first.

### 1c. The buffer half: one tab per radius, and what that costs

The buffer tab is built by fanning the *same* per-point analysis the interactive view
uses out across the Earth Engine pool — not by building one enormous `reduceRegions`.
Two reasons, and the second is the important one:

* **It is faster.** Measured 0.11 s/point fanned out against 0.39 s/point batched
  (140 points: 11 s vs 55 s).
* **It is the same code path as the screen.** A user can click one conglomerado, read the
  chart, and find those exact numbers in the file. A separate batch reducer would be a
  second implementation of the same measurement, free to drift.

**Each radius gets its own tab.** That is not only tidier — it is what sets the ceiling.
A single combined table makes the spreadsheet's 1 048 576-row limit apply to all four
radii together; one tab per radius makes it apply to the *largest radius alone*, and the
same selection fits roughly four times over. The `radius_km` column is dropped, since the
tab name carries it and it would otherwise repeat across a million rows.

The panel also lets the user export **one radius instead of all four**, which cuts rows,
Earth Engine time and file size together.

Row budgets are measured, not guessed — 40 conglomerados spread across MT, BA, RS and AM,
because the row count tracks class diversity and a sample from one município understates
it badly:

| Radius | rows/conglomerado (mean / p90 / max) | budget |
|---|---|---|
| 1 km | 158 / 249 / 341 | 280 |
| 2 km | 205 / — / 368 | 330 |
| 5 km | 284 / — / 480 | 430 |
| 10 km | 350 / 437 / 553 | 500 |
| all four | 997 / 1 406 / 1 677 | 1 540 |

A buffer row costs a **measured 46 bytes** in the finished ODS — flat from 200 k to 1 M
rows (9.2 / 23.0 / 46.0 MB), measured with realistic rounded values; unrounded random
doubles measure 61 B/row and are not what the export writes. Those two numbers are what
the panel's estimate is built from.

### 1c-bis. One limit, and it comes from the data

The buffer export is capped at **6 000 conglomerados** (`EXPORT_MAX_BUFFER_POINTS`).
The number is chosen so that **any whole biome fits**:

| Amazônia | Cerrado | Mata Atlântica | Caatinga | Pampa | Pantanal | largest UF |
|---|---|---|---|---|---|---|
| 5 801 | 4 898 | 3 511 | 2 367 | 523 | 374 | PA, 1 884 |

so every single-biome and single-state selection is within reach, at about 12 minutes.
Past that the useful unit is the whole grid, which is a batch job rather than a button.
`tests/test_exports.py` asserts the relationship rather than the number, so a change to
either the point table or the limit that stops a biome fitting fails loudly.

**The pixel and point-list halves are not capped at all** — they cover all 17 479
conglomerados in about two seconds.

Nothing else refuses. **The only hard limit in the ODS format is rows per sheet**, and
`_buffer_sheets` handles it by splitting rather than failing; there is no size limit on the
file, so none is imposed. Two earlier versions capped the selection by a row count and then
a file size, both picked by feel — enforcing constraints that did not exist.

What the panel does instead is report, before you commit: estimated time, rows, file size,
and how many tabs it will come to. Above `EXPORT_WARN_FILE_MB` (default 25) it adds a
warning, because one thing here *is* real — `rx.download` delivers the file as a base64
`data:` URI inside the WebSocket event, so a large export is held whole in memory three
times over (server bytes, server base64, browser) and very large data URIs are handled
poorly by some browsers. That is a caution, not a refusal; the user decides.



The budgets sit a little above p90 rather than at the worst case, because an underestimate
is **not fatal**: a radius that still overflows is split into `buffer_10km_2`,
`buffer_10km_3` … rather than refused. An estimate that comes in low must not destroy an
export that has already cost minutes of Earth Engine time.

When a selection does not fit, the message names a radius that *would* — the remedy is
usually "ask for one buffer instead of four", and refusing without saying so leaves the
user to guess. The whole grid at 10 km would still be ~8.7 M rows and half an hour; that
is a batch job, not a button, and the panel says so instead of hanging.

Partial failure does not abort the export. A conglomerado whose query fails is named in
the `metadados` tab and the rest of the file is written; three bad points out of five
hundred should cost three points, not the download.

### 1d. Delivery

`rx.download` carries the bytes inside the event payload, so a file costs roughly 4/3 of
its size on the WebSocket. That is fine at the sizes the cap allows (~14 MB at 1 500
conglomerados) and is a second reason not to simply raise it: past this scale the
*delivery* becomes the problem, and the answer there is a background job writing to
object storage.

---

## 2. The ODS writer

`services/ods.py`, ~150 lines, no dependency.

The obvious choice — `pandas.to_excel(engine="odf")` — builds the whole document as an
in-memory DOM and degrades superlinearly:

| Rows | odfpy | `services/ods.py` |
|---|---|---|
| 5 000 | 1.3 s | — |
| 20 000 | 7.1 s | 0.1 s |
| 60 000 | 41.9 s | — |
| 600 000 | (not attempted) | **3.9 s, 14 MB** |

An ODS file is a ZIP holding a few XML parts, and a table of plain values is a trivial
subset of the schema, so `content.xml` is streamed straight into the archive. Linear,
constant-rate, and no intermediate structure held in memory.

It supports strings, numbers and blanks. No styling, no formulas, no dates-as-dates. If
that ever needs to change, that is the moment to reach for a real library rather than to
grow this one. `tests/test_exports.py` reads every assertion back with **odfpy**, an
independent implementation — a hand-rolled format is exactly the kind of thing that works
on the author's machine and produces a file LibreOffice refuses to open.

---

## 2b. File-by-file field notes

### `ponto_pixel` / `pixel_por_ano`
A single 30 m pixel is a noisy thing: one misclassified year reads as a transition that
never happened. Every export carrying a pixel tab repeats that warning in `metadados`,
next to a pointer at the buffer tabs, which aggregate thousands of pixels.

### `buffer_XXkm` / `buffers`
Long format, not wide-by-year: 40 years × ~15 classes × 4 buffers is a natural long
table, and wide-by-year breaks the moment the year range changes. `pixels` is included
alongside `area_ha` because it is what was actually measured — area is derived from it
via decision D3, and constraint **C6** means the reader should be able to see both.

## 3. Provenance

The `metadados` tab is the `Provenance` dataclass from
[02-architecture.md](02-architecture.md) §5, flattened to key/value rows — prose and pairs
rather than raw JSON, because this is the sheet somebody reads six months later to decide
whether they can defend the numbers beside it, and JSON in a spreadsheet cell is not
readable. The underlying record is still exactly this:

```json
{
  "generated_at": "2026-08-18T17:42:11Z",
  "app_version": "0.1.0",
  "point": {"lon": -49.2733, "lat": -16.6869, "source": "map_click"},
  "buffers": {"radii_km": [1, 2, 5, 10], "mode": "disc", "crs": "EPSG:4326"},
  "analyses": [
    {
      "name": "landuse_history",
      "dataset_id": "projects/mapbiomas-public/assets/brazil/lulc/collection10_1/mapbiomas_brazil_collection10_1_coverage_v1",
      "collection_version": "10.1",
      "bands": ["classification_1985", "...", "classification_2024"],
      "scale_m": 30,
      "reducer": "frequencyHistogram",
      "pixel_area_basis": "ee.Image.pixelArea",
      "max_pixels": 1e10,
      "tile_scale": 4,
      "degraded": false
    },
    {
      "name": "vegetation_age",
      "estimators": ["mapbiomas_dsv_v3", "mapbiomas_annual", "hansen_gfc"],
      "hansen_treecover_threshold": 30,
      "persistence_rule_years": 3,
      "record_start_year": 1987,
      "censoring": "right-censored at record start",
      "age_bins": [[0,5],[6,10],[11,20],[21,30],[31,40],"censored"]
    }
  ]
}
```

The same tab carries the **required attributions** for every dataset used (MapBiomas,
Hansen et al. 2013, SFB/IFN, and the SPOT licence text when those layers contributed) —
constraint **C4** — and the suggested citation. Those facts live in
`config/citation.py` so the "Como citar" dialog and every export read one source; two
copies drift.

`degraded: true` appears whenever the retry ladder in [06-ee-layers.md](06-ee-layers.md) §4
had to coarsen `scale` or raise `tileScale`. **A degraded result is exportable but must say
so** — it is a row in `metadados`, and for a selection export the count of conglomerados
that needed a retry is recorded too.

---

## 4. Chart export

Every chart has a save control; the drawer also has an "export all charts" action.

| Format | Use | How |
|---|---|---|
| **PNG** | Default, presentations | Plotly's client-side `toImage` |
| **SVG** | Publication figures, editable in Illustrator/Inkscape | Plotly `toImage` |
| **HTML** | Interactive, self-contained | Plotly `writeHtml` — hover and zoom survive |
| **CSV** | The chart's own data | Same file as §2 |

**Rendering is client-side.** Plotly's browser export produces exactly what the user sees,
which is the point of a "save this chart" button. It also keeps `kaleido`, `matplotlib` and
a headless Chrome out of the server image — Yvynation carries all three for its batch
render lane and they are the single most fragile part of that deployment
(a silent v0→v1 kaleido API break took out its render path once). Naturametrics has no
batch lane in v1 and therefore no reason to inherit that.

Options at export: dimensions (preset + custom), scale factor (1× / 2× / 3× for print),
light or dark background, and title/caption on or off. Filenames are deterministic:
`<point_id>_<chart>_<buffer>_<timestamp>.<ext>`.

> ⚠️ If server-side rendering is ever needed (scheduled reports, a future batch mode), read
> Yvynation's `utils/ee_concurrency.py` kaleido docstring **first** — it documents both
> kaleido major-version concurrency models and why the obvious approaches deadlock.

---

## 5. Interaction

The export panel is a **dialog in the header**, beside "Como usar" and "Como citar" —
not another sidebar section. The sidebar already carries five layer controls and a
four-level filter cascade; a checklist below them would push everything else off screen.

- The study-point download is one button and needs no options: everything in it was
  already computed to draw the chart.
- The selection download has a three-item checklist, each labelled with what it costs.
  The buffer item disables itself above the cap and the panel explains why, with the
  numbers, rather than failing after the user has waited.
- Progress is reported as `done/total` conglomerados during the fan-out, and the result
  line names the file and its size — a silent download is indistinguishable from a
  failure.
- Nothing is recomputed for the study-point export. If it is not on screen, it is not in
  the file.

---

## 6. Deliberately deferred

**Chart images** (§4) are still to build; the data behind every chart is already
exportable.

**The whole grid at buffer resolution** — all 17 479 conglomerados × 4 buffers × 40 years,
~10.5 M rows — remains out of scope for an interactive download, for the two independent
reasons in §1c and §1d: it exceeds what a spreadsheet can hold, and it exceeds what an
event payload should carry. The shape it would take is clear enough (a background job
writing to object storage, and a link when it is done), and nothing built here has to be
revisited to add it: the fan-out in `selection_buffer_frame` already produces the rows,
and only the sink would change.

This does not reopen the "no batch processing" non-goal in
[01-premises.md](01-premises.md) §3. A bounded, synchronous fan-out over a filtered
selection is still one interaction the user waits on; a batch engine is a queue, a
scheduler and a retry policy, and none of those exist here.
