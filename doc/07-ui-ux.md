# 07 — UI / UX

## 1. Shape of the app

One workspace screen. Everything happens there; `about` is the only other route in v1.

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Naturametrics          [ basemap ▾ ]        [ PT | EN ]     [ ? ] [ ⇩ ]  │
├──────────────┬────────────────────────────────────────────────────────────┤
│              │                                                            │
│   SIDEBAR    │                        MAP                                 │
│              │                                                     ┌────┐ │
│  ○ Layers    │            ● study point                            │Lgd │ │
│  ○ Analysis  │           ◌ 1 ◌ 2  ◌ 5   ◌ 10 km                    │ +  │ │
│  ○ Age       │                                                     │year│ │
│  ○ IFN       │                                                     └────┘ │
│  ○ Export    │                                                            │
│              ├────────────────────────────────────────────────────────────┤
│              │  RESULTS  ▲ (collapsible, resizable)                        │
│              │  [ Land use history | Vegetation age | EVI series ]         │
│              │  ▮▮▮▮▮▮▮▮▮▮ stacked columns 1985 → 2024 ▮▮▮▮▮▮▮▮▮▮          │
└──────────────┴────────────────────────────────────────────────────────────┘
```

The map is the largest element at all times. The results drawer opens on first analysis
and can be collapsed back — the user must always be able to get a full-height map.

## 2. The primary interaction

```
       ┌─────────────────────────────────────────────┐
       │  Click the map, or pick an IFN point        │
       └──────────────────┬──────────────────────────┘
                          ▼
       marker drops · four buffer rings draw immediately
       (local geometry — no server round-trip, so this is instant)
                          ▼
       results drawer opens with skeleton loaders
                          ▼
       land-use history arrives ──┐
       vegetation age arrives ────┼── each renders as it lands, independently
       imagery/EVI arrive ────────┘
```

**The rings must appear before any query returns.** Buffer geometry is computed in the
browser from the click coordinates; waiting on Earth Engine to draw a circle would make the
app feel broken. The EE geometry used for analysis is built server-side from the same
coordinates and radii, so the two never disagree.

Re-clicking while a query is in flight cancels the old result rather than queueing it
([06-ee-layers.md](06-ee-layers.md) §5b).

## 3. Legend + year control

The single most-used control after the map itself, so it lives **on the map**, not in the
sidebar.

```
┌──────────────────────────────────┐
│  MapBiomas  2024            [×]  │
│  ├────────────●───────────────┤  │   ← slider, 1985 … 2024
│  1985                     2024   │
│  [◀] [▶] [▶‖]  step / play       │
├──────────────────────────────────┤
│  ■ Forest Formation      412 ha  │   ← only classes present in view
│  ■ Savanna Formation     180 ha  │      click a swatch → isolate class
│  ■ Pasture               301 ha  │      areas from the current buffer
│  ■ Soybean                88 ha  │
│  … 6 more                        │
├──────────────────────────────────┤
│  opacity ├─────●────┤     0.8    │
└──────────────────────────────────┘
```

- Slider is **instant** because all 40 year tile URLs are prefetched on click
  ([06-ee-layers.md](06-ee-layers.md) §5b). If it stutters, the prefetch regressed — fix
  that rather than debouncing the slider.
- Play steps ~2 years/second, pausable. This is the teaching feature.
- Legend lists **only classes present in the current view**, with their areas from the
  active buffer — a full 60-class legend is unusable and misleading.
- Clicking a class isolates it on the map and highlights its band in the chart.

## 4. Charts

### Land-use history — the signature view
Stacked columns, **one column per year, 1985–2024**, height = 100 % of buffer area (or
absolute hectares, toggleable), segments coloured with the **official MapBiomas palette**.
Buffer selected by a segmented control (1 / 2 / 5 / 10 km) or shown as small multiples.

Hovering a year previews that year on the map; clicking pins it. That linkage is what makes
the chart and map feel like one instrument.

### Vegetation age — the honest view
Because of right-censoring ([10-forest-age.md](10-forest-age.md) §5.1), this panel has a
mandatory shape:

```
┌────────────────────────────────────────────────────────────┐
│  Vegetation age — 5 km buffer                              │
│                                                            │
│  Median age of dated vegetation      14 years              │
│  Older than the record (≥40 y)       62 %  ← always shown  │
│  Total natural vegetation         4 820 ha                 │
│                                                            │
│   ha ▲                                                     │
│      │                                      ▓▓▓▓▓          │
│      │   ▒▒                          ▒▒     ▓▓▓▓▓          │
│      │   ▒▒   ▒▒    ▒▒       ▒▒      ▒▒     ▓▓▓▓▓          │
│      └───0-5──6-10──11-20──21-30───31-40───≥40 ────────▶   │
│                                          "no conversion    │
│                                        observed since 1985"│
│   ▒ dated   ▓ censored                                     │
│                                                            │
│  Confidence:  high 71 % · medium 22 % · low 7 %      [ⓘ]   │
│  Burned ≥1× since 1985: 18 % · last fire 2019              │
│  Forest formations ▮ / natural non-forest ▯ shown separately│
└────────────────────────────────────────────────────────────┘
```

Non-negotiable in this panel:
- the censored bar is **visually distinct**, not the last step of a continuous ramp;
- its label is textual (*"no conversion observed since 1985"*), never a number;
- the censored share sits **next to** the median, not in a tooltip;
- forest formations and natural non-forest are separated, the latter labelled **"time since
  last observed conversion"** rather than "age";
- an `ⓘ` opens the method summary and its limitations, linked to the about page.

### EVI series
Line chart, 16-day MODIS composites, buffer-selectable. The 1 km series carries a visible
"only ~50 MODIS pixels — noisy" warning.

## 5. Sidebar panels

| Panel | Contents |
|---|---|
| **Layers** | Land cover (MapBiomas year, DSV, change), Forest (Hansen tree cover / loss year / gain, GLAD), Age (age, establishment year, confidence, disagreement), Imagery (S2, Landsat, MODIS EVI, SPOT 2008 ×3), Fire. Each with opacity + an ⓘ giving source, date and licence. |
| **Analysis** | Study-point coordinates (editable — paste lat/lon), buffer radii, disc/ring mode, MapBiomas collection version, analysis scale. |
| **Age** | Hansen tree-cover threshold, persistence rule, age bin edges, which class groups count as natural. Every one of these changes the answer, so they are exposed rather than hidden. |
| **IFN** | Filters (estado / bioma / status), text search on `ua`, result count, scrollable list. Selecting a row flies the map to it and runs the analysis. Derived-status explanation inline. |
| **Export** | Choose buffers and analyses, then download a **grouped ZIP** (`point.csv` + one directory per buffer) or a **flat long-format CSV**. Every export carries `provenance.json` + `README.txt`. See [11-exports.md](11-exports.md). |

## 5b. Saving charts

Every chart carries a save control in its corner; the results drawer has an "export all
charts" action next to it.

```
┌── Land use history — 5 km ─────────────────── [⇩] ─┐
                                                 │
                          ┌──────────────────────┴──┐
                          │  PNG    presentation    │
                          │  SVG    publication     │
                          │  HTML   interactive     │
                          │  CSV    the data        │
                          ├─────────────────────────┤
                          │  size   [1200×700 ▾]    │
                          │  scale  [1× 2× 3×]      │
                          │  bg     [light | dark]  │
                          │  ☑ include title        │
                          └─────────────────────────┘
```

Rendering is **client-side** (Plotly `toImage`), so the saved image is exactly what is on
screen. Downloads announce themselves with the filename — a silent download reads as a
failure.

## 6. Feedback and failure

- **Every** long operation shows what it is doing ("Reducing 40 years over 4 buffers…"),
  not a bare spinner.
- Failures are sentences, not stack traces: *"No cloud-free Sentinel-2 image in this
  window — try widening the date range."*
- Clicking outside Brazil is detected before querying: *"MapBiomas covers Brazil only."*
- A buffer with no natural vegetation reports *"no natural vegetation in this buffer"* —
  never "0 years".
- Disabled-by-licence layers (SPOT) explain why they are disabled, with a link.

## 7. Bilingual from the start

PT and EN, switchable in the header. **Every user-facing string goes through an i18n key
from the first commit** — Yvynation's four-language corpus was retrofitted and it was a
week of tedium.

Structure: a small `translations/` package, `pt.py` and `en.py`, dict-based, **PT as the
source language** (the domain is Brazilian; IFN and MapBiomas terminology is native
Portuguese) with EN as the translation. Note this is the opposite of Yvynation, which
falls back to EN. Coverage is checkable with a `python -m naturametrics.translations`
entry point, same as Yvynation's.

Domain terms stay Portuguese even in EN: *bioma*, *unidade amostral*, *conglomerado*.

## 8. Visual language

Carried from Yvynation so the two feel related without being confusable: Radix-themed
Reflex components, light surface, map-dominant layout, restrained chrome. Divergence:
Naturametrics uses a **distinct accent colour** and its own wordmark — a user must never be
unsure which app they are in.

## 9. Accessibility notes

- MapBiomas colours are prescribed and **not colour-blind safe**; the legend always pairs
  swatch with label, and the chart offers a class-isolate mode as the non-colour path.
- The age ramp is one we choose, so it **must** be perceptually uniform and CVD-safe
  (viridis-family), with the censored class distinguished by *both* hue and hatching.
- Full keyboard path for point entry (coordinate input) so the map click is never the only
  way in.
