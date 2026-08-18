# 10 — Vegetation Age Estimation

**Goal:** for each buffer, estimate **how long the forest and natural vegetation has been
there**, and report it as an age-class distribution plus a map layer.

This is the analytical centre of gravity of the application. It is also the part where it
is easiest to produce a confident-looking number that is wrong, so the caveats in §5 are
not an appendix — they are part of the specification.

---

## 1. What "age" can and cannot mean here

We are inferring age from **satellite-observed land-cover time series**. That bounds what
is knowable:

- The estimate is **time since the last observed establishment or disturbance**, not
  stand age in the silvicultural sense.
- MapBiomas begins in **1985**. Anything continuously vegetated since then has an age that
  is **right-censored at ~40 years**. Primary Amazon forest is centuries old; the data can
  only say *"≥ 40 years / no observed conversion since 1985."*
- Hansen GFC's disturbance record begins in **2001** (with a `treecover2000` baseline), so
  it censors at ~25 years.

**Therefore the output is always two quantities, never one:**

1. the **age distribution of vegetation with an observed establishment date**, and
2. the **fraction that is censored** (older than the record).

Reporting a single "mean forest age" that silently folds censored pixels in at 40 years
would be wrong, and wrong in the direction of making old forest look young. See §5.1.

---

## 2. Class groups: what counts as forest, what counts as natural

Driven by config (`config/mapbiomas.py`), never hard-coded at call sites. Based on the
MapBiomas Collection 10.1 legend:

| Group | MapBiomas classes | Note |
|---|---|---|
| **Forest formations** | 3 (Forest Formation), 4 (Savanna Formation), 5 (Mangrove), 6 (Floodable Forest), 49 (Wooded Sandbank Vegetation) | Class 4 is *cerrado sensu stricto* — woody but not "forest" by Hansen's definition. Keep it separate-able. |
| **Natural non-forest** | 11 (Wetland), 12 (Grassland), 29 (Rocky Outcrop), 32 (Hypersaline Tidal Flat), 50 (Herbaceous Sandbank Vegetation), 13 (Other Natural Formation) | "Age" is a weaker concept here — see §5.5 |
| **Planted forest** | 9 (Forest Plantation) | **Excluded from natural vegetation.** Its "age" is a rotation, not succession. Reported separately. |
| **Anthropic** | 15, 18–21, 35–48, 62, 24, 30, 31, 9 … | Not aged; used to detect conversion |
| **Water / no data** | 26, 33, 34, 0, 27 | Masked out entirely |

⚠️ These groupings must be reviewed against the official MapBiomas Collection 10.1 legend
document before implementation — Yvynation's `MAPBIOMAS_LABELS` contains duplicated and
legacy codes (e.g. 1/2/3 all mapping to forest-ish labels, 29 appearing twice) and is a
convenience table, not a normative legend. Tracked as **D6**.

---

## 3. Three estimators

### E1 — MapBiomas *Deforestation & Secondary Vegetation* (primary source) ★

| | |
|---|---|
| Asset | `projects/mapbiomas-public/assets/brazil/lulc/collection10_1/mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3` |
| Bands | `classification_1987` … `classification_2024` |
| Resolution | 30 m |

Class codes (already validated in Yvynation's `deforestation_timeline.py`):

| Code | Meaning |
|---|---|
| 0 | Other / não aplicável |
| 1 | Anthropic (stable) |
| **2** | **Primary vegetation (stable)** |
| **3** | **Secondary vegetation (stable)** |
| 4 | Deforestation in primary vegetation *(event year)* |
| **5** | **Secondary vegetation regrowth** *(event year)* |
| 6 | Deforestation in secondary vegetation *(event year)* |
| 7 | Not applied / noise |

**This is the best available basis and should be the primary estimator**, because
MapBiomas has already done the temporal consolidation that E2 would have to reinvent:

- Pixels currently class **2** → **primary, censored**: no conversion observed in the
  record. Age reported as *"≥ 38 years (no conversion since 1987)"*.
- Pixels currently class **3** → **secondary**: age = `current_year −
  (year of the most recent class-5 regrowth event at that pixel)`.
- A pixel with a class-4 or class-6 event after its last regrowth is currently anthropic
  and drops out of the natural mask.

EE formulation — the "most recent event year" reduction:

```python
YEARS = range(1987, 2025)
dsv = ee.Image(DSV_ASSET)

# Year-valued image per event class: the year where the event occurred, else 0.
def event_year(code):
    return ee.ImageCollection([
        dsv.select(f'classification_{y}').eq(code).multiply(y).rename('y')
        for y in YEARS
    ]).max()                       # most recent occurrence

regrowth_year = event_year(5)      # last regrowth
```

### E2 — MapBiomas annual LULC series (fallback / cross-check)

The Collection 10.1 coverage image (40 bands, 1985–2024) is used when the DSV product does
not apply — notably for **natural non-forest** classes, which the DSV product does not
track. Same reduction shape:

```python
BANDS  = [f'classification_{y}' for y in range(1985, 2025)]
mb     = ee.Image(MAPBIOMAS_ASSET)

natural = {y: mb.select(f'classification_{y}').remap(NATURAL_CODES, [1]*len(NATURAL_CODES), 0)
           for y in range(1985, 2025)}

# Establishment = natural this year AND not natural the previous year
establishment_year = ee.ImageCollection([
    natural[y].And(natural[y-1].Not()).multiply(y).rename('y')
    for y in range(1986, 2025)
]).max()
```

⚠️ **A persistence rule is mandatory here.** Single-year class flicker is common in the raw
annual series, and a naive `neq` transition detector will read noise as regrowth. Require
**≥ 3 consecutive natural years** for an establishment to count (and symmetrically for a
conversion). This is exactly the work the DSV product does for forest, which is why E1
leads.

### E3 — Hansen Global Forest Change (independent disturbance bound)

| | |
|---|---|
| Asset | `UMD/hansen/global_forest_change_2025_v1_13` (`ee.Image`) |
| Bands | `treecover2000` (0–100 %), `lossyear` (0, 1–24 → 2001–2024), `gain` (0/1, 2000–2012), `datamask` |
| Resolution | 30 m |

Hansen contributes **one thing very well: an independent, globally consistent
stand-replacement disturbance date.** Use it that way and no further:

- `treecover2000 ≥ THRESHOLD` (default **30 %**, configurable) and `lossyear == 0` →
  tree cover present and undisturbed since 2000 → **age ≥ 25 years** (censored by Hansen).
- `lossyear == k` → disturbance in year `2000 + k`. If the pixel is natural vegetation
  today, its age is **at most** `current_year − (2000 + k)`.
- `gain == 1` → tree cover gain 2000–2012, but with no year resolution and lower
  reliability; treat as a weak corroborating signal only, never as a date.

Yvynation's GLAD GLCLU2020 layers (`projects/glad/GLCLU2020/v2/LCLUC_{2000..2020}`) are
5-yearly land-cover strata — useful as an additional map layer and a coarse cross-check,
but too coarse in time to date establishment. Not part of the age estimator.

---

## 4. Fusion

The governing principle is simple and conservative:

> **The most recent disturbance observed by *any* source bounds the age from above.**

```
establishment_year = max(
    E1_regrowth_year,                       # MapBiomas DSV regrowth (0 if none)
    E2_establishment_year,                  # annual-series establishment (0 if none)
    E3_hansen_loss_year + 1,                # first plausible year of re-establishment
)

age = current_year − establishment_year          if establishment_year > 0
    = CENSORED (≥ current_year − record_start)   otherwise
```

### Agreement / confidence flag

Reported alongside every age, and rendered as a map layer in its own right:

| Confidence | Condition |
|---|---|
| **High** | E1 and E3 agree within ±2 years, or both independently say "censored" |
| **Medium** | Only one source has a date; the other is silent (e.g. outside Hansen's window) |
| **Low** | Sources disagree by > 5 years, or the pixel's current class differs between MapBiomas and Hansen tree-cover |

Disagreement is **information, not failure**: Hansen loss with no MapBiomas conversion is
a strong degradation/selective-logging signal, and the map should show it rather than
average it away.

### Fire as a qualifier, not an age reset

MapBiomas Fire Collection 4 is already configured in Yvynation
(`fire_frequency_1985_2024`, `year_last_fire`). A burned forest usually keeps its
MapBiomas class, so fire is invisible to the age estimator while being highly relevant to
what the vegetation actually *is*. Attach both as **qualifiers** to each age class:
`% of the age class that burned ≥1 time`, and `year of last fire`. Do **not** silently
treat fire as an establishment event — whether it should reset age is ecologically
context-dependent (fatal in Amazon forest, routine in Cerrado). Tracked as **D7**.

---

## 5. Caveats that must reach the user, not just the code

### 5.1 Right-censoring is the dominant caveat
Most natural vegetation in a typical Brazilian buffer will be censored. The UI must:
- label the censored class explicitly (*"≥40 y — no conversion observed since 1985"*),
  never as a numeric bin;
- report the **censored share as a headline number** next to any summary statistic;
- prefer **median age of dated vegetation** + censored share over a "mean age";
- never compute a mean that includes censored pixels at their floor value.

### 5.2 Hansen forest ≠ MapBiomas forest
Hansen's `treecover2000` is a **tree canopy cover percentage**, definition-agnostic: it
includes eucalyptus plantations, tree crops, and dense cerrado above the threshold, and it
excludes open natural formations that MapBiomas correctly calls natural. This is why
Hansen is used **only for disturbance dates** here, never to define what is forest. The
threshold (default 30 %) is a user-visible parameter, because the choice materially changes
results in Cerrado and Caatinga.

### 5.3 Hansen "loss" is disturbance, not deforestation
It records stand-replacement change from any cause — clear-cut, plantation harvest,
severe fire, windthrow, flooding. In plantation landscapes it fires on every rotation.

### 5.4 Annual classification flicker
Addressed by the persistence rule in E2 and by preferring E1. Any implementation that
detects transitions with a bare year-to-year comparison will overestimate young vegetation.

### 5.5 "Age" is a weak concept for natural non-forest
Cerrado grassland, campos and wetlands are fire-adapted and naturally dynamic; "time since
last conversion" is meaningful, "age" is not. For these classes the UI must use the label
**"time since last observed conversion"**, and the age chart should visually separate them
from forest formations.

### 5.6 Degradation is invisible
Selectively logged or repeatedly burned forest retains its class and therefore its age. The
fire qualifier (§4) partially mitigates this; the limitation must still be stated.

### 5.7 Resolution and edges
Everything is 30 m. A 1 km buffer is ~3 500 pixels — small enough that edge effects and a
handful of misclassified pixels move percentages visibly. Report pixel counts alongside
areas so the reader can judge.

---

## 6. Outputs

### Per buffer
- **Age-class distribution** — ha and % across configurable bins. Default:
  `0–5 | 6–10 | 11–20 | 21–30 | 31–40 | ≥40 (censored)`, plus a separate
  `planted forest` bar and a `not natural` remainder.
- **Median age of dated vegetation** + **censored share** + **total natural area**.
- **Confidence breakdown** — % high / medium / low.
- **Fire qualifier** — % of natural area burned ≥1×, year of last fire.
- Split by class group (forest formations vs natural non-forest) — never pooled silently.

### Map layers
| Layer | Rendering |
|---|---|
| **Vegetation age** | Sequential palette over dated ages, plus a distinct flat colour for censored — a continuous ramp that runs off the end of the scale would misrepresent censoring |
| **Establishment year** | Same data, viridis by year — often more legible for change reading |
| **Confidence** | 3-class categorical |
| **Source disagreement** | Binary highlight — Hansen loss without MapBiomas conversion |

### Query cost
All three estimators reduce to **year-valued images** built with `ee.ImageCollection(...).max()`
server-side, then a **single `reduceRegions`** across the four buffers with a histogram over
age bins. Under Partner tier the three estimators are also **issued concurrently** rather
than sequentially, so the fused product costs roughly one round-trip of wall-clock time.
See [06-ee-layers.md](06-ee-layers.md) §4 and §5b.

---

## 7. Validation plan

The estimator must be checked before it is believed:

1. **IFN plots as reference.** Phase 4 delivers thousands of field points with recorded
   land use. The `ifn-uso-da-terra-por-uf` product gives observed land-use class per
   *subparcela*. Comparing estimated age/class at IFN points against field observation is
   the strongest validation available and is a genuine research output in itself.
2. **Known-history sites.** A handful of well-documented regrowth areas and recent
   clearings, checked by eye against the SPOT 2008 mosaic and Sentinel-2.
3. **Internal consistency.** Total natural area from the age product must reconcile with
   the Phase 1 MapBiomas history for the same year, to within rounding. A mismatch means a
   masking bug and should be an automated test.
4. **Sensitivity.** Vary the Hansen threshold (10/30/50 %) and the persistence rule
   (2/3/5 years) and report how much the age distribution moves. If it moves a lot,
   that fact belongs in the UI.
