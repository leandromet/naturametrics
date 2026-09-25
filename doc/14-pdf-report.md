# 14 — PDF report

> **A report is the export you hand to someone who will read it, not reprocess it.** The ODS
> holds the numbers, and the per-chart icons export one figure at a time. The report lays out
> *what was analysed, where, from which data, and what it shows*, in one file.

Planned on **2026-09-24**. It is planned together with the same feature in Camposcope
(`doc/13-pdf-report.md`) and Yvynation (`reflex_app/docs/PDF_REPORT.md`). The three reports
share one layout, one kit and one set of image rules (§2). This app holds the **canonical copy
of the kit**. The decision is recorded as **D11** in [09-open-decisions.md](09-open-decisions.md).

---

## 1. Purpose and scope

Today the export dialog offers an ODS workbook and a **"Relatório em HTML"**:
`services/report.py::study_point_report_html`, with Plotly inlined and print CSS. The HTML
report has three problems:

- **No maps.** A study-point report without a map of the point and its buffers is missing its
  first figure.
- **Portuguese only in practice.** It uses inline `lang == "pt"` switches, the table headers come
  from Portuguese dicts, `PIXEL_CAVEAT` and the provenance labels exist only in Portuguese, and
  the footer always uses `DATA_SOURCES`.
- **It reports the wrong thing in multi mode.** The button is gated on `has_result`
  (`state/_analysis.py:53`), and `toggle_multi_mode` does not clear it
  (`state/_conglomerado.py:437-474`). With a multi-selection on screen, the report describes the
  *previous single point*.

**This plan adds a PDF and rebuilds the HTML report on the same content model (R4).** Both
formats gain maps, explanatory paragraphs, an "about this report" list and correct English.

**Scope of the first release (R8, decided 2026-09-24):**

| Selection | v1 | Why |
| --- | --- | --- |
| **Study point**, from a map click or a conglomerado click, with its buffer radii (`BUFFER_RADII_KM` = 0.5/1/2/5/10 km, `config/settings.py:72`) | ✅ | The core loop |
| **Manual multi-selection** of conglomerados, in the `sum` or `full_area` view (`multi_view_mode`, `_conglomerado.py:133`) | ✅ | "The current selection" on screen |
| Drawn/KML region (`state/_geometry.py`, results at `GEOMETRY_REGION_RADIUS_KM = 0.0`) | ⏸ | Needs its own layout: one zone, not rings. The button is disabled with a reason |
| Filter-defined selection (região/bioma/UF/município) | ⏸ | Up to about 6 000 points means an EE fan-out; the ODS covers it |
| Pasted user points (`state/_user_points.py`) | ⏸ | Same reason as filter selections |
| `/canada` | ⏸ | A separate root state and its own charts; a later port once the kit has settled |

**Existing bugs this work fixes first** (they matter on their own and ship even if the PDF
slipped):

1. Gate the report on the **view mode** and read the mode-aware accessors, not `self._history`
   (`state/_export.py:408`). The accessors are `_chart_records()` (`_analysis.py:407`),
   `_age_buffer_records()` (610), `_landscape_metrics_records()` (623), `_biomass_records()`
   (760) and `_veg_compare_records()` (829).
2. Take the radii **from the data**, not from `BUFFER_RADII_KM` (`services/report.py:181`).
   Full-area mode carries only the largest radius.
3. Draw rings from `buffer_overlays` (`_analysis.py:76`), which is exactly what the map shows in
   every mode.

**Status (2026-09-24): bugs 1 and 2 are fixed** in today's HTML report.

- `state/_export.py` picks every dataset and its provenance with `_mode_pick`, the same three-way
  switch as the charts. In multi mode it passes a `selection` descriptor, so title, subtitle,
  metadata, overlap caveat and file name (`…_selecao_N_…`) describe the selection.
- Change-since-2008 and connectivity are left out for a selection, since they are never computed
  for one.
- Drawn regions are refused with `report_region_unsupported`.
- The button is gated on `report_available`, and a badge (`report_subject_label`) shows what will
  be reported.
- `services/report.py::_radii_in` takes the radii from the frames.
- Tests: `tests/test_report_mode_switch.py`, plus three regressions in `tests/test_report.py`.

Bug 3 belongs to the map work and lands with the model rebase.

**Status (2026-09-24, later): the model rebase is in, bug 3 included.** The report maps draw
their rings and points from `buffer_overlays` (multi mode's `buffer_circle` entries become
geodesic circles in `services/report.py::map_frame`). The old HTML-only generator,
`download_study_point_report` and `_build_study_point_report` are gone; see §11 for what is
verified.

---

## 2. The shared report kit (same text in all three apps)

> **This section is copied word for word** into Naturametrics `doc/14-pdf-report.md`,
> Camposcope `doc/13-pdf-report.md` and Yvynation `reflex_app/docs/PDF_REPORT.md`. Edit it in
> Naturametrics only, then copy it again. Everything outside §2 is specific to each app.

### 2.1 What the kit is, and why it is copied into each app

Naturametrics, Camposcope and Yvynation are three umaterra apps, and all three need the same
kind of document. That is a readable report with metadata first, then maps, charts and
tables, joined by short paragraphs. If each app built its own, they would drift apart within a
month. So the page model, the renderers, the map framing and the image rules live in one
package, **`report_kit`**, which knows nothing about any app.

| Copy | Path |
| --- | --- |
| **Canonical** | `/server/naturametrics/naturametrics/report_kit/` |
| Vendored | `/server/camposcope/camposcope/report_kit/` |
| Vendored | `/home/leandromb/google_eengine/yvynation/reflex_app/yvynation/report_kit/` |

`scripts/sync_report_kit.py` in Naturametrics copies the canonical tree into the other two
apps and rewrites `report_kit/MANIFEST`, which holds the sha256 of every file.
`tests/test_report_kit_manifest.py` in each app recomputes the hashes and fails on any
difference. **A fix made in a vendored copy would be lost at the next sync, so kit fixes go into
the canonical copy only.** This is the same copy-with-provenance pattern already used for
`ods.py`, `provenance.py` and `tiles.py`. A shared pip package was rejected: it would add a
private package source to three Cloud Build pipelines for about 1 500 lines of code.

**Rules for kit code:**

- Relative imports only.
- Never import the host app or `reflex`, and never import `ee` at module level. `ee` is
  imported lazily inside `maps.fetch_thumbnail`.
- Must run on **Python 3.11** (Yvynation's image). No nested same-quote f-strings and no
  `type X = …` aliases.
- Dependencies: `reportlab>=4.2,<5` and `pillow>=10`. pandas is imported lazily, only by
  `Table.from_frame`.

### 2.2 Decisions shared by the three apps (agreed 2026-09-24)

| # | Decision | Chosen | Rejected, and why |
| --- | --- | --- | --- |
| R1 | PDF engine | **reportlab**: a pure wheel with no system packages, and native tables that split across pages | Chromium printing: Naturametrics and Camposcope deliberately carry no Chromium. WeasyPrint: needs pango/cairo in the image and cannot run Plotly. matplotlib `PdfPages`: poor text layout |
| R2 | Chart images, Naturametrics and Camposcope | **Rendered by the browser**: `Plotly.toImage` of figure JSON sent by the server (§2.7) | kaleido + Chromium: about 300 MB of image, the most fragile part of Yvynation's deploy, and it reverses Naturametrics `doc/11-exports.md` §4. matplotlib re-draws: duplicate chart code, and the charts would no longer match the screen |
| R3 | Chart images, Yvynation | **Its existing server-side kaleido path** (`export_service._plotly_to_png_bytes`) | Browser capture: batch runs have no browser |
| R4 | HTML and PDF | **One content model, two renderers** (`render_pdf`, `render_html`), so the two formats cannot disagree | Two independent generators, as today, would drift |
| R5 | Map backdrop | **Earth Engine only**, via `getThumbURL`, using the same palettes as the screen | Google or Esri tiles: redistributing them inside a PDF is a terms-of-service problem |
| R6 | Explanatory text | **Deterministic templates for each language**, fed from the frames the charts already use | An LLM: not reproducible, and it could produce claims the data does not support |
| R7 | Sharing the code | **Vendored copies checked against a manifest** (§2.1) | A private pip package |
| R9 | Image resolution | **Screen quality, sized to the page: 150 dpi at the slot's size** (§2.5) | 300 dpi print: files 4× larger for a document read on screen |

(R8 is specific to Naturametrics' scope and is in its own doc.)

### 2.3 Content model: `report_kit/model.py`

Each app builds a `Report`, and the kit renders it. The model uses plain dataclasses and
contains no Reflex or Earth Engine objects.

```python
Slot = Literal["full", "half"]            # 170 mm or 82 mm wide (style.py)

@dataclass
class Brand:        accent: str; app_line: str        # e.g. "#2f7d4f", "umaterra · Camposcope"
@dataclass
class ReportMeta:   app: str; app_url: str; app_version: str; title: str; subject: str
                    lang: str                          # "pt" | "en" | "es" | "fr"
                    generated_at: datetime             # tz-aware UTC
                    brand: Brand
@dataclass
class Report:       meta: ReportMeta; sections: list[Section]
@dataclass
class Section:      title: str; blocks: list[Block]; key: str = ""   # key feeds ContentsList

# Blocks
Paragraph(text: str, lead: bool = False)             # **bold** / *italic* only; the kit escapes all else
KeyValues(rows: list[tuple[str, str]], caption: str = "")
Figure(key: str, caption: str, slot: Slot = "full", aspect: float = 0.56,
       fig_json: dict | None = None,                 # HTML: interactive Plotly
       png: bytes | None = None,                      # PDF: the rasterised chart
       unavailable_reason: str = "")                  # neither → a "figure unavailable" placeholder
MapFigure(composition: MapComposition, caption: str, slot: Slot = "full")
LocatorMap(geometry: dict, label: str, slot: Slot = "half")   # GeoJSON of the object
Table(columns: list[str], rows: list[list], caption: str,
      align: list[str] | None = None,                 # "l" / "r" per column
      max_rows: int = 40, note: str = "",             # overflow → "n more rows in the appendix/ODS"
      decimals: list[int | None] | None = None)       # numeric cells are locale-formatted by the kit
Table.from_frame(df, headers: dict[str, str], caption, **kw)
Callout(text: str, kind: Literal["disclosure", "note", "warning"] = "note", title: str = "")
ContentsList(items: list[ContentsItem])
ContentsItem(title: str, status: Literal["included", "not_run", "unavailable", "excluded"],
             reason: str = "")
ProvenanceTable(rows: list[dict])                     # each app's Provenance.to_dict()
Citation(text: str, sources: list[str], attributions: list[str])
SideBySide(left: Block, right: Block)                 # two half-slot blocks on one row
PageBreak()
```

Figures, maps and locators share one "Figure n" counter, and tables have their own. Captions
are prefixed by the kit ("Figura 3 —", "Table 2 —"). `ProvenanceTable` shows `name`,
`dataset_id`, `bands`, `scale_m`, `reducer`, `degraded` and `computed_at`, with `notes`
underneath. A degraded row is always shown, never hidden.

### 2.4 The same outline in every report

1. **Title block.** App line, report title, subject, the time it was generated (UTC and local
   time of the requested language), app version and URL.
2. *(Camposcope only)* **Disclosure callout.**
3. **Identification.** `KeyValues` of the object's metadata, `SideBySide` with the `LocatorMap`.
4. **About this report.** A `ContentsList`: every section the app can produce, marked included,
   not run, unavailable or excluded (by a checkbox), with the reason. Then one paragraph giving
   the period, the zones or buffers, and how to read the document: *data, not a verdict*.
5. **Maps.**
6. **Analysis sections**, one per dataset, in each app's on-screen order. Each has a one-sentence
   intro (what the dataset is), the figure, a summary table, and a *reading* paragraph built
   from the numbers.
7. **Methods and provenance.** `ProvenanceTable`.
8. **Sources, citation and attributions.** In the report's language, including "Contains
   modified Copernicus Sentinel data {year}" and "Landsat: USGS/NASA" whenever those backdrops
   appear.
9. **Appendix** (optional). Full tables. Always off in batch runs.

**Page, `style.py`.**

- A4 portrait, margins 20 mm on both sides and 18 mm at top and bottom, text width **170 mm**.
- Noto Sans (OFL, in `report_kit/fonts/`): body 9.5 pt on 13.5 pt leading, H1 16 pt, H2 12.5 pt,
  captions 8.5 pt.
- The header band on pages 2 onwards carries the app line in the accent colour, with the subject
  on the right.
- Footer: `umaterra · <App> · <url> — página x de y — gerado em <date>`, in the report's
  language.
- Tables: `LongTable(repeatRows=1)`, zebra rows, numbers right-aligned and formatted for the
  locale.

Noto Sans covers Guarani and Portuguese diacritics (ỹ, g̃). reportlab does no text shaping, so
combining marks can sit slightly off. This is accepted.

The system Noto Sans has **no − (U+2212), →, ≥, ≤ or ↳**, and reportlab drops a missing glyph
silently: "−3,2" printed as "3,2". Since kit v0.1.1, `fonts/NotoSansMath-Subset.ttf` (35 KB,
arrows, math operators and the true minus) is registered as a fallback. `pdf._glyph_fallback`
wraps any character the main font lacks in that font, and canvas strings (header, footer, scale
bar) get ASCII stand-ins. Apps may use these characters freely.

### 2.5 Images: screen quality, sized to the page (R9)

The reports are read on screens. Every raster is produced **for the slot it fills, at 150 dpi**,
never at print resolution and never larger than its slot.

| Slot | Width | Pixels at 150 dpi | Chart layout in CSS px (96 dpi) | Plotly/kaleido `scale` |
| --- | --- | --- | --- | --- |
| `full` | 170 mm | ≈ 1004 | 643 × (643·aspect) | 150/96 = **1.5625** |
| `half` | 82 mm | ≈ 484 | 310 × (310·aspect) | 1.5625 |
| full map | 170 × 110 mm | ≈ 1004 × 650 | — | — |

- **Charts are laid out at their true on-page CSS size and rasterised at `scale = 150/96`.**
  Plotly's pixel font sizes then print at about their nominal point size next to the 9.5 pt body
  text. A chart laid out 1000 px wide and shrunk to 170 mm would print its 12 px labels at about
  6 pt.
- `images.chart_opts(slot, aspect) -> {"width", "height", "scale"}` gives the numbers above to
  both chart paths (browser and kaleido).
- `images.prepare_figure(fig_json, slot, aspect) -> dict` works on a copy of the figure dict and
  needs no plotly import. It:
  - sets width and height;
  - sets a white paper and plot background (on-screen charts are transparent);
  - raises fonts to at least 10 px;
  - moves legends with more than six entries below the plot;
  - removes `updatemenus` and `sliders`.
- `images.fit_image(data, slot_mm, kind)`:
  - reads the PNG IHDR or JPEG SOF header **before** decoding, and refuses anything over 40 MP;
  - downsamples to the slot's size at 150 dpi;
  - re-encodes imagery (`kind="photo"`) as **JPEG q≈80**, and class rasters and charts
    (`kind="flat"`) as **PNG**, palette-quantised when there are 256 colours or fewer.
  - Both renderers call it, so an oversized input can never inflate the file.
- **Budget:** a synthetic report with 8 figures and 4 maps must stay **at or under 3 MB**, and a
  kit test asserts it.

### 2.6 Maps: `report_kit/maps.py` and `locator.py`

- **`MapView.from_geojson(geoms, slot, margin=0.08)`.** Computes the bounding box in EPSG:3857,
  padded and stretched to the slot's aspect ratio, so the fetched raster fills the frame exactly.
  It exposes `bbox_lonlat`, `bbox_3857`, `px` and `metres_per_px`.
- **`fetch_thumbnail(image, view, fmt, *, cache_key)`** is the kit's **only network call**. It
  calls `image.getThumbURL({"region": ee.Geometry.Rectangle(view.bbox_lonlat, None, False),
  "dimensions": f"{view.px_w}x{view.px_h}", "crs": "EPSG:3857", "format": fmt})` and makes an
  HTTP GET (`urllib`, 60 s timeout). Both dimensions are passed, so the raster is exactly the
  view's size. Results are cached in the process by `(cache_key, bbox rounded to 1e-5, px, fmt)`.
  - The caller must have initialised Earth Engine (its own `get_ee()`).
  - The caller must run it in an executor, never on the event loop.
  - In Yvynation it runs **before** entering a render lane.
- **`imagery_backdrop(view, year) -> ee.Image | None`** picks the backdrop by map extent:

| Longest side of the view | Backdrop | Visualisation |
| --- | --- | --- |
| ≤ 50 km (property, rings, buffers) | `COPERNICUS/S2_SR_HARMONIZED` masked with `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` `cs ≥ 0.60`, median of the dry season (Jun–Sep) of `year`, falling back to the full year | B4/B3/B2, 0–3000, JPEG |
| 50–300 km (territories) | `LANDSAT/COMPOSITES/C02/T1_L2_ANNUAL`, image for `year` | red/green/blue, 0–0.3, gamma 1.2, JPEG |
| > 300 km | none: class layers and the locator only | — |

- **Class layers** (MapBiomas, Hansen, change masks and so on) are **provided by the app** as an
  already-visualised `ee.Image`, built by the *same* `<layer>_image()` function its tile layer
  uses (see §6 of each app doc). The PDF and the screen then share their pixels and palettes.
  They are fetched as PNG with transparency.
- **`MapComposition`** contains:
  - `view`;
  - `backdrop` (JPEG bytes or `None`);
  - `overlays` (PNG bytes, bottom to top);
  - `vectors`: `VectorLayer(geojson, stroke, width_pt, dash=None, fill=None, label="")`;
  - `clip_to` (GeoJSON that masks the overlays to the object's shape, or `None`);
  - `legend`: `LegendItem(color, label, kind="fill"|"line")`;
  - `attribution`.

  **Outlines and rings are drawn as vectors by the renderer, not painted in Earth Engine.** They
  stay sharp at any zoom, no geometry is sent to Earth Engine, and the thumbnail cache works per
  bounding box.
- **Frame furniture**, drawn by both renderers:
  - a thin frame;
  - a scale bar with a round length of about ⅕ of the width, corrected by cos(latitude);
  - a north arrow;
  - the legend **below** the map, never on top of it;
  - the attribution in 7 pt.

  The PDF renderer uses a reportlab `Drawing`. The HTML renderer uses the `<img>` layers plus
  inline SVG.
- **`LocatorMap`.** Draws Brazil's states from the kit's `data/br_uf.simplified.geojson`
  (copied from Camposcope `data/uf_boundaries.simplified.geojson`, 99 KB) as vectors. It
  highlights the object's state or states and marks the object (a point, or its bounding box
  when larger than 2 % of the map).

### 2.7 Chart capture in the browser (Naturametrics and Camposcope)

The kit provides the JavaScript and the job store. Each app writes the three handlers. The
flow was verified against Reflex 0.8.27: `state.js` L354–379 awaits a Promise returned by
`call_script`, and `reflex/utils/format.py:588` `format_queue_events` builds callbacks.

```text
[PDF button] ─► start_report("pdf")                 (normal, non-background handler: snapshot + job)
                 ├─ figs = {key: prepare_figure(fig_json, slot, aspect)}   ← same charts.* builders as the screen
                 ├─ job = JobStore.create(client_token, expected=figs.keys())
                 └─ return [rx.call_script(build_capture_script(figs, callbacks, opts)),   # no callback
                            State.build_report(job.id, "pdf")]                          # background
browser:  await window.Plotly (≤ 8 s) → for each key: try { d = await Plotly.toImage(fig, opts) }
          catch { d = "" }; if d.length > 900 000 retry at scale 1; cb[key](d)   ← one socket event per chart
          ─► receive_report_chart(job_id, key, data)  → JobStore.put(...)   (validates, stores bytes)
build_report(job_id, fmt)  [background]
   ├─ starts the EE thumbnails in an executor immediately (they overlap the browser's rendering)
   ├─ polls JobStore every 250 ms until every key is resolved or 15 s + 2 s × n_figures elapse
   ├─ a missing or failed key → Figure(png=None, unavailable_reason=…)   (never hangs)
   └─ builds the Report → render_pdf → rx.download(data=…, filename=…, mime_type="application/pdf")
```

- **Callbacks** are created in the app, because the kit cannot import Reflex. For each key:
  `str(format_queue_events(State.receive_report_chart(job_id, key), args_spec=lambda d: [d]))`.
  They are passed to `build_capture_script(figs, callbacks, opts)` as a `{key: js_source}`
  mapping.
- **One script, not N `call_script`s.** Each `call_script` holds the page's event queue while its
  Promise is pending, and a rejected Promise never fires its callback. One script with
  per-chart callbacks avoids both problems.
- **`JobStore`** (`browser_capture.STORE`) is a module-level dict with a lock and a 10-minute
  TTL, pruned on every access. Its API is `create(token, keys) -> job_id`,
  `put(job_id, key, data_url, token) -> bool`, `progress(job_id) -> (got, expected)`, `done()`,
  and `take(job_id) -> ({key: png | None}, {key: error})`. `wait_deadline_s(n)` gives the build
  task's timeout.
  It holds images outside Reflex state, because even `_backend` vars are pickled on every event.
  `put()` rejects:
  - a client token that differs from the job's;
  - data without the `data:image/png;base64,` prefix;
  - anything over 3 MB decoded;
  - a PNG whose IHDR exceeds 4000 × 4000.

  An empty string means the browser failed, and is recorded as such.
- **Incoming socket limit.** Reflex caps incoming messages at `REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE`
  (default 1 000 000 bytes). Beyond it, engine.io drops the connection *silently*. R9-sized charts
  are 50–200 KB, and the Dockerfile sets `REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE=4000000` as headroom.
- **`window.Plotly`** exists only after the first `rx.plotly` has mounted, because its bundle loads
  lazily. The report block mounts a hidden 1×1 `rx.plotly` so that the bundle is present, and the
  8 s wait plus the placeholder cover everything else.
- **The HTML format needs no capture.** It embeds `fig_json` directly, so `start_report("html")`
  goes straight to `build_report`.
- **Background-handler rules still apply:** no `type(self)` in background tasks, and every state
  write inside `async with self`. Wrap the snapshot in the app's `plain()`.

### 2.8 Explanatory text

- Each app has `services/report_text.py`: pure functions `(frames…, lang) -> str` returning
  one to three sentences. They are held as one template dict per language, with the app's
  reference language as fallback. `report_kit/text.py` formats numbers, areas, percentages
  and dates for pt, en, es and fr. The kit's own fixed strings are in those four languages too.
- **Describe, never judge.**
  - The sentences state quantities, changes over the period, and comparisons with the rings or
    the buffer.
  - No causal claims ("because of…").
  - No legal, compliance or valuation vocabulary.
  - Camposcope enforces this with a test (its doc, §9). The other two follow it by review.
- Every number in a sentence comes from the same frame the chart or table in that section was
  drawn from. **Nothing is recomputed at export.**

### 2.9 The export UI block: same anatomy in the three apps

```text
┌ Relatório  ·  Report ───────────────────────────────────────────┐
│ A laid-out document: identification, maps, charts and tables    │
│ with short explanations. Language = the interface's.            │
│ [✓] Mapas   [✓] Gráficos   [✓] Tabelas-resumo   [ ] Apêndice    │
│ [ ] GBIF  (where the app has it)                                │
│ ( PDF )  primary          ( HTML )  secondary                   │
│ Gráficos 3/7 · Mapas 2/3 · Montando PDF…      ← stage line      │
│ ⓘ reason when disabled (no result yet / wrong mode / running)   │
└──────────────────────────────────────────────────────────────────┘
```

**Common names:**

- State vars: `exp_report_maps`, `exp_report_figures`, `exp_report_tables`,
  `exp_report_appendix` (Naturametrics and Camposcope already have the figures and tables
  ones), plus `report_busy`, `report_stage` and `report_error`.
- Handlers: `toggle_exp_report_*` and `start_report(fmt: str)`, where `fmt` is a string because
  of the Reflex arg-type rule.
- Translation keys use the prefix `report_`.

**File names:**

- `<app>_<object-slug>_<YYYYMMDD-HHMM>.pdf` (or `.html`), for example
  `camposcope_MT-5108501-CBE0F5_20260924-1530.pdf`.
- Batch runs: `territory/{slug}/{slug}_report.pdf`.

### 2.10 Kit tests (canonical, run through each vendored copy)

**Status (2026-09-24): kit v0.1.0 is built** in the canonical location. The tests below pass
(`tests/test_report_kit.py`, 23 tests, plus `tests/test_report_kit_manifest.py`), and a report
also renders under a real CPython 3.11.15. A synthetic 7-page report with every block type,
6 charts, a 4000 px backdrop and a 120-row table is 0.37 MB and renders in 0.4 s.
`scripts/sync_report_kit.py --check` verifies all copies. Both repositories' `.gitignore`
ignored any file named `MANIFEST`; `!**/report_kit/MANIFEST` now overrides that.

- A synthetic `Report` using **every block type** produces bytes starting with `%PDF` and one
  self-contained HTML file with no external URLs.
- A 4000 px input image is embedded at the slot's pixel size or smaller, and a JPEG backdrop
  stays JPEG.
- 8 figures + 4 maps + 3 tables produce a file of **3 MB or less**.
- A 120-row `Table` spans pages and repeats its header row.
- `fmt_num(1234.5)` gives `1.234,5` in pt, es and fr style and `1,234.5` in en. The kit strings
  exist in all four languages.
- `Figure(png=None)` renders the placeholder and does not raise.
- `JobStore` rejects wrong tokens, prefixes and sizes, and an oversized IHDR; a job times out
  into "unavailable" entries.
- `MapView` aspect and scale-bar arithmetic are checked at the equator and at 30°S.
- The suite runs under Python 3.12 (Naturametrics, Camposcope) **and 3.11** (the Yvynation
  venv).

---

## 3. Report outline (Naturametrics)

This fills in the common outline of §2.4. The **active radius** is the one selected in the results
drawer, and every per-radius figure is drawn at that radius. Tables cover every radius present in
the data.

### 3a. Study point

| # | Section | Blocks |
| --- | --- | --- |
| 1 | Identification | `KeyValues`: coordinates (decimal and DMS), origin (map click or conglomerado *n*), UF / município / bioma (conglomerado only; a plain click shows "—"), buffer radii and shape (disc or ring, D2), period 1985–2024, analysis time (UTC). `SideBySide` with the `LocatorMap` |
| 2 | About this report | `ContentsList` of every section below and its status. For example, connectivity is "not run" until its button is pressed, and GBIF is "excluded" when unticked. Then one paragraph on how to read it |
| 3 | Maps | (a) Sentinel-2 dry-season backdrop + rings; (b) MapBiomas 2024 + rings; (c) change 2008→2024 (loss / regeneration / stable, `services/change_mask.py`) + rings |
| 4 | Land-cover history | Figure `land_cover_history_figure` at the active radius; a table of per-radius first→last year per class (`services/exports._buffer_summary`); reading paragraph |
| 5 | The point's own pixel | A table of class runs (`year_from–year_to: class`) from `_pixel`, plus `PIXEL_CAVEAT` as a `Callout(note)` |
| 6 | Vegetation age | Figures `forest_age_line_figure` (point) and `forest_age_histogram_figure` (active radius); `censored_share_pct` stated in the text (constraint **C5**) |
| 7 | Change since 2008 | Figure `change_bar_figure`; table of `perda_ha / regeneracao_ha / estavel_ha` per radius |
| 8 | Biomass | Figure `biomass_history_figure` |
| 9 | Landscape metrics | Table (`METRIC_COLUMNS`), plus connectivity when it has been run |
| 10 | IBGE × MapBiomas | Figure `ibge_comparison_figure` |
| 11 | GBIF *(optional)* | Table of `gbif_buffer_rows` per radius |
| 12 | Methods and provenance | `ProvenanceTable` of every `Provenance` present |
| 13 | Sources and citation | `CITATION_TEXT` plus `DATA_SOURCES` **or `DATA_SOURCES_EN`**, chosen by language |
| 14 | Appendix *(optional)* | Full land-cover and age tables per radius |

### 3b. Manual multi-selection

| # | Section | Blocks |
| --- | --- | --- |
| 1 | Identification | N conglomerados, view mode (`sum` / `full_area`), radii present, period. `Table` of points (conglomerado, UF, município, bioma, lat/lon from `_multi_meta` and `_multi_coords`). `LocatorMap` of their bounding box |
| 2 | About this report | `ContentsList`. **Not computed for a selection**, and listed as "unavailable" with that reason: change since 2008, point age, pixel series, connectivity |
| 3 | Callout | The overlap caveat, always shown in `sum` mode |
| 4 | Maps | MapBiomas 2024 with the points and rings over the selection's extent. **No imagery when the extent exceeds 300 km** (§2.6) |
| 5–8 | Aggregates | Land cover, age histogram, biomass, landscape metrics, IBGE comparison. Each uses the same mode-aware accessors that draw the on-screen chart |
| 9 | Per point | `Table`: natural-vegetation % in the first and last year at the active radius, one row per conglomerado, from `_multi_frames` |
| 10+ | Provenance, sources, appendix | As in 3a |

### 3c. Explanatory text: examples (`services/report_text.py`, pt reference, en fallback to pt)

| Section | pt | en |
| --- | --- | --- |
| Land cover | "No raio de 5 km, a formação florestal ocupava 3.412 ha (43,4 %) em 1985 e 2.118 ha (27,0 %) em 2024, uma redução de 1.294 ha. A classe que mais cresceu foi Soja (+1.020 ha)." | "Within the 5 km buffer, forest formation covered 3,412 ha (43.4%) in 1985 and 2,118 ha (27.0%) in 2024, a decrease of 1,294 ha. The class that grew most was Soybean (+1,020 ha)." |
| Age | "Metade da vegetação nativa no raio de 1 km tem até 18 anos; 12 % dela está no limite da série (idade censurada: pelo menos 38 anos)." | "Half of the native vegetation within 1 km is 18 years old or younger; 12% of it sits at the series limit (censored age: at least 38 years)." |
| Change | "Desde 2008, 84 ha deixaram de ser vegetação natural no raio de 2 km e 31 ha voltaram a sê-lo." | "Since 2008, 84 ha within 2 km stopped being natural vegetation and 31 ha became natural again." |
| Multi caveat | "Os totais somam os buffers de cada conglomerado; onde eles se sobrepõem, a mesma área é contada uma vez por conglomerado, portanto o total não é a área da união." | "Totals add up each conglomerado's buffers; where they overlap the same ground is counted once per conglomerado, so the total is not the area of their union." |

---

## 4. Where each block comes from

| Block | Source in the code |
| --- | --- |
| Identification | `study_lat`, `study_lon`, `point_source`, `point_conglomerado`, `point_uf`, `point_municipio`, `point_bioma`, `buffer_shape` (`state/_point.py:29-43`); `point_identity_label` (`_point.py:155`) |
| Radii | Keys present in the frames, never `BUFFER_RADII_KM` (§1, bug 2) |
| Rings (vectors) | `buffer_overlays` (`state/_analysis.py:76`); `role: "buffer_circle"` entries carry centre and radius (multi mode) |
| Land cover | `_chart_records()` (`_analysis.py:407`) → `charts.land_cover_history_figure` (`components/charts.py:38`) |
| Summary per radius | `services/exports._buffer_summary` (`exports.py:169`) |
| Pixel | `_pixel`, `_pixel_provenance`; `PIXEL_CAVEAT` (`exports.py:68`) |
| Age | `_age_point`, `_age_buffer_records()` (610) → `forest_age_line_figure` (charts.py:163), `forest_age_histogram_figure` (225) |
| Change | `_change_stats` (`_analysis.py:98`) → `change_bar_figure` (charts.py:263) |
| Biomass | `_biomass_records()` (760) → `biomass_history_figure` (charts.py:343) |
| Landscape / connectivity | `_landscape_metrics_records()` (623), `_connectivity` (112) |
| IBGE comparison | `_veg_compare_records()` (829) → `ibge_comparison_figure` (charts.py:418) |
| GBIF | `gbif_buffer_rows` (`state/_gbif.py:171`) |
| Multi-selection | `_multi_meta`, `_multi_coords`, `_multi_frames`, `multi_view_mode` (`state/_conglomerado.py:78-159`) |
| Provenance | `services/provenance.Provenance.to_dict()` of every result; `exports._provenance_rows` (87) holds today's labels, to be moved into the kit's `ProvenanceTable` |
| Citation | `config/citation.py`: `CITATION_TEXT`, `DATA_SOURCES` (58), `DATA_SOURCES_EN` (148), `APP_URL` |

Figures are built **on the server** from these frames by the same `charts.*` functions the screen
uses, then passed through `report_kit.images.prepare_figure`. The report needs every radius and
both modes, so it cannot rasterise whatever divs happen to be mounted.

---

## 5. Chart path

This app uses browser capture, exactly as in §2.7.

- `start_report("pdf")` builds the figure dict.
- The kit's `build_capture_script` renders the charts in the browser.
- Each result comes back through `receive_report_chart(job_id, key, data)`.
- `build_report(job_id, "pdf")` waits on the `JobStore`.
- Background handlers use `state_class(self)` (`state/_proxy.py:27`). `tests/test_state_event_refs.py`
  already bans `type(self).`.

The HTML format skips capture.

---

## 6. Maps

Class layers must come from the same image builders as the tiles, so the report and the screen
cannot show different palettes. `services/change_mask.py` already has the right shape
(`change_mask_image` L67, `change_mask_spec` L96). Apply it to `services/layers.py`:

| Map | Image builder | Status |
| --- | --- | --- |
| MapBiomas year | `mapbiomas_image(year)`, split out of `mapbiomas_spec` (L84) | **to split** |
| Change 2008→2024 | `change_mask.change_mask_image` | exists |
| Imagery | `report_kit.maps.imagery_backdrop(view, year)` (Sentinel-2, `config/datasets.SENTINEL2` thresholds) | kit |
| (later) biomass, Hansen, IBGE | split `biomass_spec` (207), `hansen_*_spec` (249/282) and `ibge_vegetation_spec` (180) when a report section needs a map | deferred |

- The view is the largest radius present plus the kit's margin, or the points' extent in multi
  mode.
- Every Earth Engine entry point calls `get_ee()` first (the stale-tab lesson, doc/11).

---

## 7. UI

The **"Relatório / Report"** block (§2.9) becomes its own section of `exportar_dialog()`
(`components/exports.py:290`). It replaces the HTML subsection inside `_study_point_section`
(L91-111) and reports **what is on screen**:

- the badge reads *Ponto de estudo · …* or *Seleção · N conglomerados*;
- it is disabled, with a reason, when there is no result, while running, or in region mode.

**Implementation notes:**

- Checkboxes: `exp_report_maps`, `exp_report_figures`, `exp_report_tables`,
  `exp_report_appendix` and a new `exp_report_gbif` (GBIF has no export toggle today; its own ODS lives in `state/_gbif.py`).
- A hidden 1×1 `rx.plotly` forces the Plotly bundle to load (§2.7).
- **Translations** go in `translations/pt.py` and `en.py` with the prefix `report_`. Check
  coverage with `python -m naturametrics.translations`.
- Mind the `tr[...].format()` trap: format counts in a computed var, or use the `_tr_radii`
  pattern (`components/exports.py:24-36`).

---

## 8. Delivery

`rx.download(data=bytes, filename=…, mime_type="application/pdf")`. This is the same mechanism as
the ODS and today's HTML report (about 4/3 the size over the socket, `state/_export.py:17-21`).

- The PDF is at most 3 MB by R9.
- The HTML inlines Plotly (about 4.5 MB, as it does today).

A PDF this size does not need a download route.

---

## 9. Guardrails

- **C4, licences.** Every backdrop and layer in a map adds its attribution line: Copernicus
  Sentinel-2, MapBiomas Collection 10.1 (CC BY-SA 4.0), and so on.
- **C5, uncertainty.** An age figure without `censored_share_pct` in its sentence does not ship.
- **C6, reproducibility.** `ProvenanceTable` is always present, and degraded results are
  flagged.
- **Nothing is recomputed at export**, and the report waits for in-flight age and change fetches
  (up to 20 s), exactly as `download_study_point` does (doc/11 §1a).
- Explanatory text describes and never judges (§2.8). "Restoration candidate" appears only as
  the change mask's own legend label.

---

## 10. Files to add or change

| File | Change |
| --- | --- |
| `naturametrics/report_kit/**` | **New, canonical** (Step 2, one owner) |
| `scripts/sync_report_kit.py` | New: copies to Camposcope and Yvynation and rewrites `MANIFEST` |
| `naturametrics/services/report.py` | Becomes `build_study_point_report(...) -> Report` and `build_selection_report(...) -> Report`; the HTML comes from `report_kit.render_html` |
| `naturametrics/services/report_text.py` | New: the explanatory templates (pt, en) |
| `naturametrics/services/layers.py` | Split `mapbiomas_image` out of `mapbiomas_spec` |
| `naturametrics/state/_export.py` | New vars (§2.9); `start_report`, `receive_report_chart`, `build_report`; mode-aware gate; remove `download_study_point_report` and `_build_study_point_report` (L372-449, 678-715) |
| `naturametrics/components/exports.py` | `_report_section()` (§7) |
| `naturametrics/translations/pt.py`, `en.py` | `report_*` keys; retire the old `check_report_*` / `download_report_button` keys |
| `requirements.txt` | `reportlab>=4.2,<5`, `pillow>=10` |
| `Dockerfile` | `ENV REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE=4000000`; the "no chromium/kaleido" comment stays true |
| `tests/test_report.py` | Rewritten against the model (below) |
| `tests/test_report_kit_manifest.py`, `tests/test_report_kit.py` | New (kit tests live here, canonically) |
| `doc/09`, `doc/03`, `doc/11`, `doc/README.md` | D11; Phase 6 entry; §4 cross-link; index rows 13–14 |

---

## 11. Tests and the done test

**Offline** (`pytest -m "not ee"`):

- `build_study_point_report` on synthetic frames gives the §3a section order. Unticked sections
  are `excluded`, and missing results are `not_run` or `unavailable`.
- `build_selection_report` in `sum` and `full_area` modes: the overlap caveat is present in
  `sum` mode, and radii come from the data (full area has one).
- **Regression:** with multi mode on and a stale single-point result, the report is the
  selection's, never the point's.
- The English report contains no Portuguese template text. Verbatim identifiers are exempt.
- `test_app_builds` (the page renders) and `test_state_event_refs` (no `type(self).`) pass.
- The kit tests (§2.10) and the manifest test pass.

**Live** (`-m ee`, run locally):

1. One conglomerado click in Mato Grosso.
2. A 5-point multi-selection across two biomes.
3. For each, open the PDF at 100–150 % zoom.

**Done test.** A user clicks a conglomerado, opens *Exportar* and presses **PDF**. Within about
20 s they get a file of 3 MB or less. Its first page names the conglomerado, município and
biome, and lists what the report contains. Every chart matches the screen, and every map has a
legend, a scale bar and its attributions. Switching to English and repeating gives an entirely
English document. With a 5-point multi-selection on screen, the same button gives the
**selection** report with the overlap caveat, and never the previous point.

---

**Status (2026-09-24): implemented for R8 (study point + manual selection).**

- Code: `services/report.py` (snapshot → `ReportData`, `figure_specs`, `fetch_report_maps`,
  `build_study_point_report` / `build_selection_report`, `render_report`, `report_filename`),
  `services/report_text.py` (pt/en templates), `services/layers.py::mapbiomas_image`,
  `services/change_mask.py::change_mask_vis`, `state/_export.py` (`start_report` →
  optional `wait_for_report_inputs` (≤ 20 s) → `begin_report` → capture script +
  `build_report`; `receive_report_chart`; a token-bound `_PendingStore` holds the snapshot
  between the two handlers; map thumbnails start on a worker pool in `begin_report`, so they
  overlap the browser's chart rendering), `components/exports.py::_report_section`.
  `state/_gbif.py` now records where the GBIF survey ran (`_gbif_buffer_point`) so a stale
  survey is not reported under a new point.
- Offline tests: `tests/test_report.py` (rewritten against the model: §3a order, statuses,
  C5 sentence, radii from data, selection/full-area, English without Portuguese template
  text, both formats render, PDF ≤ 3 MB) and `tests/test_report_mode_switch.py` (the state
  snapshot in multi mode is the selection's; the pending job is bound to its client token).
- Live (EE) smoke, run by script rather than through the app: a Mato Grosso study point
  (−12.55, −55.72) with real frames and real maps (Sentinel-2, MapBiomas 2024, change
  2008–2024), charts rasterised by the kit's own `build_capture_script` in headless Chromium,
  PDF 0.56 MB / 11 pages; a 4-point, two-biome selection in English, PDF 0.42 MB.
- **Not yet verified: the Reflex round trip in a browser** (call_script → per-chart socket
  events → `receive_report_chart` → `build_report` → download). Run the app and press PDF.
- Known gaps: the age-histogram bin labels come from the data in Portuguese (the screen shows
  the same), so an English report still has "anos" on that axis.

## 12. Deliberately deferred

- Drawn/KML regions, filter-defined selections and pasted user points (§1 table).
- `/canada`: port once the kit has settled; `canada/` has its own charts and state.
- A per-chart "include in report" toggle. Sections are all-or-nothing in v1.
- Scheduled or batch reports. This app has no batch lane, and R2 would have to be revisited.
- Maps for biomass, Hansen and IBGE (§6).
