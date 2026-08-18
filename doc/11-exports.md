# 11 — Exports

Everything the app computes must leave the app. The rule from constraint **C6**
([01-premises.md](01-premises.md)) applies to every file written here:

> **No export without provenance.** A CSV that does not say which dataset, which bands,
> which geometry, which scale and which reducer produced it is not reusable, and
> six months later nobody — including its author — can defend the numbers in it.

---

## 1. Shape of a data export

An analysis produces results at **five nested scopes**: the study point itself, and one
per buffer. Exports keep those **as separate groups**, never flattened into one
undifferentiated table.

```
naturametrics_<pointid>_<timestamp>/
├─ README.txt                  ← human-readable provenance + what each file is
├─ provenance.json             ← machine-readable, the same facts
├─ point.csv                   ← the study point: coordinates, context, point-level values
├─ buffer_01km/
│  ├─ landuse_history.csv      ← year × class × area
│  ├─ landuse_summary.csv      ← one row per class: first year, last year, net change
│  ├─ vegetation_age.csv       ← age class × area, censored share, confidence
│  └─ evi_series.csv           ← date × mean EVI  (only if MODIS was requested)
├─ buffer_02km/  …same four…
├─ buffer_05km/  …
├─ buffer_10km/  …
├─ geometry.geojson            ← the point + all four buffer polygons, one FeatureCollection
└─ charts/                     ← only if chart export was requested
   ├─ landuse_history_05km.png
   └─ vegetation_age_05km.png
```

Delivered as a **single ZIP**. The user asked for "all points in separate groups"; the
directory-per-buffer layout is what makes that legible in a file manager, in a shell, and
to `pandas.read_csv` in a loop.

### Also offered: one flat file

Some workflows want a single table. So alongside the grouped ZIP there is a **single
long-format CSV** with a `scope` column:

```csv
scope,buffer_km,year,class_id,class_name,area_ha,area_pct
point,,2024,3,Formação Florestal,,
buffer,1,1985,3,Formação Florestal,238.41,75.9
buffer,1,1986,3,Formação Florestal,236.02,75.1
...
buffer,10,2024,15,Pastagem,9184.33,29.2
```

Long format, not wide: 40 years × ~15 classes × 4 buffers is a natural long table, and
wide-by-year breaks the moment the year range changes. Both forms come from the same
in-memory DataFrame, so they cannot disagree.

---

## 2. File-by-file

### `point.csv`
One row. The study point and everything that is a property *of the point* rather than of
an area.

| Column | |
|---|---|
| `point_id` | Stable id — `ua` when an IFN point, else `lat_lon` rounded |
| `longitude`, `latitude` | WGS84, 6 dp |
| `source` | `map_click` \| `ifn` \| `coordinate_entry` |
| `ifn_ua`, `ifn_uf`, `ifn_bioma`, `ifn_municipio`, `ifn_status_derivado` | Populated only for IFN points; `status_derivado` carries its "derived, not official" note in `README.txt` |
| `mapbiomas_class_<year>` | The class **at the point pixel** for each requested year |
| `vegetation_age_years` | Age at the point pixel, or `CENSORED` |
| `establishment_year` | or empty when censored |
| `age_confidence` | `high` \| `medium` \| `low` |
| `hansen_lossyear` | Raw Hansen loss year at the pixel, `0` = none |

A single 30 m pixel is a noisy thing; `README.txt` says so explicitly next to this file.

### `buffer_XXkm/landuse_history.csv`
The signature table — the data behind the stacked columns.

```csv
year,class_id,class_name_pt,class_name_en,area_ha,area_pct,pixel_count
1985,3,Formação Florestal,Forest Formation,238.41,75.90,2649
1985,15,Pastagem,Pasture,52.17,16.61,580
```

Long format. `pixel_count` is included because it is what was actually measured — area is
derived from it, and constraint **C6** means the reader should be able to see both.

### `buffer_XXkm/landuse_summary.csv`
One row per class: `area_first_year`, `area_last_year`, `net_change_ha`, `net_change_pct`,
`year_of_max`, `year_of_min`. Convenience only — fully derivable from the history file.

### `buffer_XXkm/vegetation_age.csv`
Two blocks in one file, separated by a blank line and a comment header, because the
headline statistics are not the same shape as the distribution:

```csv
# distribution
age_class,label,area_ha,area_pct,pixel_count,confidence_high_pct,burned_pct
0-5,0–5 years,44.10,2.1,490,88.0,12.4
...
censored,No conversion observed since 1985,1298.55,62.0,14428,94.1,18.0

# summary
metric,value
median_age_dated_years,14
censored_share_pct,62.0
total_natural_ha,2094.3
...
```

**`censored_share_pct` is mandatory in every age export.** An age table without it invites
exactly the misreading that [10-forest-age.md](10-forest-age.md) §5.1 exists to prevent.
Forest formations and natural non-forest are written as separate rows with a `class_group`
column — never silently pooled.

### `geometry.geojson`
Point + four buffer polygons in one FeatureCollection, each with `radius_km`,
`buffer_mode` (`disc`/`ring`) and its area. Lets anyone re-run the analysis elsewhere, which
is the real test of whether an export is honest.

---

## 3. Provenance

`provenance.json` is the `Provenance` dataclass from [02-architecture.md](02-architecture.md)
§5, serialised, one entry per analysis:

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

`README.txt` is the same information in prose, plus the **required attributions** for every
dataset used (MapBiomas, Hansen et al. 2013, SFB/IFN, and the SPOT licence text when those
layers contributed) — constraint **C4**.

`degraded: true` appears whenever the retry ladder in [06-ee-layers.md](06-ee-layers.md) §4
had to coarsen `scale` or raise `tileScale`. **A degraded result is exportable but must say
so**, both in the JSON and as a line in `README.txt`.

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

- Export panel in the sidebar, plus a save icon on each chart.
- The user chooses **which buffers** and **which analyses** go into the ZIP; default is
  everything computed so far. Nothing is recomputed at export time — if it is not on
  screen, it is not in the file, and the panel says which analyses are available.
- ZIP is assembled server-side and delivered via `rx.download`; large exports stream
  rather than buffering whole.
- A progress indicator for anything over a second, and an explicit success state with the
  filename — a silent download is indistinguishable from a failure.

---

## 6. Deliberately deferred

Multi-point / batch export (one ZIP covering many points, or a combined table across an
IFN filter selection) is **Phase 7**, alongside batch mode. The single-point layout above
is designed so that a batch export is the same tree one level deeper
(`<point_id>/buffer_XXkm/…`) plus a combined long-format CSV with a `point_id` column —
so choosing this structure now does not have to be revisited then.
