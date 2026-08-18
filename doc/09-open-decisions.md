# 09 — Decision Record

**All decisions below were accepted on 2026-08-18.** Each recorded recommendation is now
the chosen path; the alternatives and reasoning are kept because a decision without its
rationale is unreviewable later.

| | Decision | Chosen | Code impact |
|---|---|---|---|
| D1 | Map rendering | **A** — custom persistent Leaflet component (Folium fallback stands) | Phase 0 |
| D2 | Buffer geometry | **A** — cumulative discs by default, rings as a toggle | Phase 1 |
| D3 | Area accounting | **B** — `ee.Image.pixelArea()` | Phase 1 |
| D4 | IFN status | **A** — derived from dataset membership, labelled as derived | Phase 5 |
| D5 | EE project | **`ee-leandromet` — required**, the Partner grant is attached to it | binds deploy |
| D6 | Natural-class groups | Derive from the official Collection 10.1 legend | Phase 3 |
| D7 | Fire and age | **A** — fire is a qualifier, never an age reset | Phase 3 |
| D8 | Age bins | `0–5 \| 6–10 \| 11–20 \| 21–30 \| 31–40 \| ≥40`, user-configurable | Phase 3 |
| D9 | Catalogue format | **A** — commit the flat CSV, not GeoJSON | **applied** |
| D10 | Deployment | **Cloud Run, CD from GitHub `main`** | binds Phase 0 config |

D6 still carries three sub-questions that need the official legend document in hand — they
are marked in place. Everything else is settled.

---

## D1 — Map rendering: custom Leaflet component vs. Folium HTML
**DECIDED: A** — custom persistent Leaflet component. *Implement in Phase 0.*

Yvynation regenerates a full Folium document and drops it in an iframe via `rx.html`; every
layer change reloads the iframe and loses the viewport. Naturametrics needs a persistent
map (constraint C1) because clicking is the primary gesture and the year slider must be
smooth.

| Option | Pros | Cons |
|---|---|---|
| **A. Custom Reflex component wrapping Leaflet** *(recommended)* | Persistent map; instant layer swaps; real `on_click` event; smooth year slider | Must be written; Reflex custom components have a learning curve |
| B. Folium → `rx.html` (Yvynation's way) | Working reference two directories away; zero new concepts | Viewport lost on every change; 1–3 s per toggle; fragile cross-frame JS bridge; **year slider not viable** |

**Recommendation: A**, with B as a genuine fallback if the component fights Reflex's
renderer. Timebox the spike — if A is not working within a day, ship B and degrade the year
control to a select, then revisit.

---

## D2 — Buffer geometry: discs or rings
**DECIDED: A** — cumulative discs as default, rings as a toggle. *Implement in Phase 1.*

Yvynation uses **external rings** (donuts), because it buffers *outward from a territory
polygon* and the territory itself is analysed separately. Naturametrics buffers from a
*point*, where that reasoning does not carry.

| Option | Meaning |
|---|---|
| **A. Cumulative discs** *(recommended)* | 0–1, 0–2, 0–5, 0–10 km. "Everything within N km" — the natural reading of "a 5 km buffer around this point" |
| B. Rings | 0–1, 1–2, 2–5, 5–10 km. Non-overlapping, better for distance-decay analysis |

**Recommendation: A as default, B as a toggle.** They are the same query with different
geometry, so supporting both costs almost nothing — but the default must be discs, because
that is what a user means when they say "within 5 km". Whichever is active must be stated
on the chart, since the numbers differ substantially.

---

## D3 — Area accounting: nominal pixel area vs. `pixelArea()`
**DECIDED: B** — `ee.Image.pixelArea()` under a grouped reducer. *Implement in Phase 1.*

| Option | Method | Error |
|---|---|---|
| **A. Nominal** | `count × 0.09 ha` (Yvynation's approach) | Small in Brazil, non-zero, grows with latitude and with projection |
| **B. `ee.Image.pixelArea()`** *(recommended)* | Grouped reducer summing true pixel area | Correct; slightly more complex query |

**Recommendation: B.** The extra complexity is one reducer, and it removes a caveat we
would otherwise have to explain forever. Whichever is chosen goes into
`Provenance.pixel_area_basis` so results remain interpretable across a later change.

---

## D4 — IFN "status": derived vs. official
**DECIDED: A** — derive from dataset membership, and label it as derived everywhere it appears. Pursue B in parallel. *Applied in `scripts/fetch_ifn.py`; UI copy in Phase 5.*

No status field is published; this was checked against the CSVs, the SFB methodology page
and the SNIF portal ([05-ifn.md](05-ifn.md) §4).

| Option | |
|---|---|
| **A. Derive from dataset membership** *(recommended for v1)* | `medido_completo` / `medido_biofisico` / `socioambiental`, plus a `com_impedimento` flag |
| B. Obtain the official grid + status from SFB | Correct, but needs the theoretical 20 km lattice origin or a direct request to SFB |

**Recommendation: A now, pursue B in parallel.** A ships, provided the UI labels it as
**derived** wherever it appears. Presenting a derived flag as official IFN status would be
the wrong kind of confident.

---

## D5 — Earth Engine project
**DECIDED: `ee-leandromet`, and this is now a constraint rather than a preference.**

**The Partner tier authorisation is granted to `ee-leandromet` specifically.** A separate
project would not inherit it — it would start at contributor limits, and the whole
fan-out/prefetch design in [06-ee-layers.md](06-ee-layers.md) §1b and §5b assumes Partner
concurrency. So the earlier framing ("isolation would be nice, quota is not a concern")
had it backwards: isolation is the thing we give up, and the tier is the thing we cannot.

**What this means in practice:**

- `GCP_PROJECT_ID=ee-leandromet` everywhere, local and deployed.
- **The Cloud Run service account must be registered for Earth Engine inside
  `ee-leandromet`** (see D10). A service account in another project authenticating
  *against* `ee-leandromet` is not the same thing as one that carries the tier — verify
  the deployed app actually gets Partner concurrency rather than assuming it.
- Quota is shared with Yvynation. Still not a capacity risk at these volumes, but it is
  the first thing to check if the deployed app feels inexplicably slow during a Yvynation
  batch run.
- Usage telemetry will not separate the two apps. Accepted.

**Do not migrate to a dedicated project** unless a Partner grant is obtained for it first.

⚠️ Yvynation records the uplift as expiring **2027-02-15**. Confirm the real date for
`ee-leandromet`, and keep the design degrading to "slower but correct" if it lapses —
nothing should *break* without Partner concurrency, only slow down.

---

## D6 — MapBiomas natural-vegetation class groups
**DECIDED: derive from the official legend**, not from Yvynation's label table. *Three sub-questions below remain open pending the legend document — resolve them in Phase 3.*

The age estimator depends entirely on which classes count as forest, natural non-forest,
planted or anthropic. Yvynation's `MAPBIOMAS_LABELS` is a convenience table with
duplicated and legacy codes (1/2/3 all forest-ish, 29 twice) — usable for labelling, **not
normative** for a class-group definition.

**Recommendation:** derive the groups from the **official MapBiomas Collection 10.1 legend
document**, encode them in `config/mapbiomas.py` as explicit sets with a comment citing
the legend version, and add a test that every code in `MAPBIOMAS_LABELS` falls into exactly
one group. **Sub-questions still open** — settle them in Phase 3 with the legend document in hand:
- Does **Savanna Formation (4)** count as "forest"? It is woody, natural, and central to
  Cerrado — but Hansen's tree-cover threshold treats it inconsistently. *Suggested: its own
  sub-group, included in "natural", excluded from "forest formations" by default, toggleable.*
- Is **Forest Plantation (9)** ever shown as natural? *No — separate bar, never pooled.*
- **Mosaic of Uses (21)**: natural or anthropic? *Anthropic, but flagged, since it hides
  real natural fragments.*

---

## D7 — Does fire reset vegetation age?
**DECIDED: A** — fire is a qualifier on each age class, never an age reset. *Implement in Phase 3.*

A burned forest usually keeps its MapBiomas class, so fire is invisible to the age
estimator while being highly relevant to what the vegetation actually is.

| Option | |
|---|---|
| **A. Fire as a qualifier** *(recommended)* | Age unchanged; each age class reports % burned and year of last fire |
| B. Fire resets age | Simpler story, ecologically wrong in fire-adapted Cerrado |
| C. Biome-dependent | Reset in Amazon forest, qualifier in Cerrado |

**Recommendation: A for v1**, with C as a considered extension once there is someone to
defend the biome-specific rule. B is not defensible.

---

## D8 — Age bin edges
**DECIDED: the default below**, exposed in the Age panel. *Implement in Phase 3.*

Default proposed: `0–5 | 6–10 | 11–20 | 21–30 | 31–40 | ≥40 (censored)`. The first two bins
are narrow because early regrowth changes fastest and is where the data is most reliable.
Expose the edges in the Age panel; **the censored bin edge is not a choice** — it is set by
the record start (1985, or 1987 when the DSV product leads).

---

## D9 — Format of the committed IFN catalogue
**DECIDED: A — commit the flat CSV.** *Applied: `scripts/fetch_ifn.py` now writes `data/ifn_points.csv` (committed, 5 dp coordinates) and `data/cache/ifn_points.geojson` (gitignored working copy).*

**Measured** (`scripts/fetch_ifn.py --uf AC --uf GO --build-catalog`, 2026-08-18):

| | |
|---|---|
| Acre + Goiás | **1 074** unidades amostrais |
| GeoJSON | **303 kB** → ~282 B/point |
| Flat CSV | **112 kB** → ~107 B/point |

Extrapolating to 27 UFs at a plausible national total of 10 000–15 000 points:
**GeoJSON ≈ 3–4 MB, CSV ≈ 1.1–1.6 MB.** So the original "commit the GeoJSON" plan
**breaks its own 2 MB guard** — GeoJSON's per-feature key repetition is most of the file.

| Option | National size | |
|---|---|---|
| **A. Commit the flat CSV** *(recommended)* | ~1.1–1.6 MB | The app builds canvas circle markers from lat/lon; it never needs GeoJSON structure. Diffs readably. |
| B. Commit GeoJSON | ~3–4 MB | Over the guard, and a poor diff |
| C. Commit Parquet | ~0.3–0.5 MB | Smallest, but binary — every regeneration is an opaque blob in history |
| D. Generate at deploy time | 0 | No offline/dev convenience; adds a build step |

**Recommendation: A.** `fetch_ifn.py` already writes both, so this is a one-line change to
which path is the committed artefact. Trim coordinates to 5 dp (~1 m, far beyond what a
20 km grid needs) and drop columns the UI does not use. Re-measure once all 27 UFs are
downloaded — the extrapolation above is from two states, and Goiás is unusually dense.

Either way this stays a file, not a database: a few thousand points filter in memory
comfortably.

---

## D10 — Deployment target
**DECIDED: Cloud Run, continuously deployed from the `main` branch of the GitHub repo.**

A **new, separate Cloud Run service** — its own service, revisions and traffic split,
independent of Yvynation's — but pointed at the **same EE project `ee-leandromet`**, since
that is where the Partner grant lives (D5). Yvynation already deploys to Cloud Run and its
`CLOUD_RUN_DEPLOYMENT.md` is a working recipe, so this is both the familiar path and the
low-risk one.

**Consequences that bind implementation now, not later:**

| | |
|---|---|
| **Credentials** | Cloud Run has no ADC file, so EE auth must work through **method 1** of `ee_client.py` — `EE_PRIVATE_KEY` + `EE_SERVICE_ACCOUNT_EMAIL` from Secret Manager. That path must be exercised before the first deploy, not discovered during it. |
| **Ports** | Cloud Run injects `PORT`. Frontend binds `PORT`, backend binds a separate `BACKEND_PORT`, or both fight for the same socket. `rxconfig.py` reads both. |
| **Statelessness** | Per-session state only; nothing that assumes a single process. The tile-URL cache is per-instance and that is fine — a cache miss just re-mints a URL. |
| **The image ships the data** | `data/ifn_points.csv` is baked into the container. Reinforces **D9**: a 1.1–1.5 MB CSV in the image is fine; a 4 MB GeoJSON plus a git history of them is not. |
| **`.gcloudignore` / `.dockerignore`** | Must exclude `data/raw/`, `data/cache/`, `.venv/`, `.web/`. Without this the build context carries the raw IFN downloads. |
| **Git remote** | The repo has **no remote configured yet**. Add the GitHub remote before any of this can work. |

**Still open, and worth deciding before the first deploy:** whether CD runs through Cloud
Build triggers or GitHub Actions, and whether `main` deploys straight to production or to a
staging revision with traffic migration. Neither blocks Phase 0.

⚠️ **Nothing is pushed or deployed without being asked.**

