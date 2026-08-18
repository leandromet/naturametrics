# 08 — Development Environment

## 1. Prerequisites

| Tool | Version | Note |
|---|---|---|
| Python | **3.12** | System python3 on this machine is already 3.12.3 |
| Node | ≥ 18 | Reflex installs and manages its own frontend toolchain |
| git | any | Repo at `/server/naturametrics`, branch `main`, no remote yet |

Earth Engine credentials already exist locally at `~/.config/earthengine/credentials`
(ADC path), which is what `initialize_earth_engine()` method 2 uses.

## 2. Virtual environment

Naturametrics gets **its own** venv. Do not reuse Yvynation's
(`/home/leandromb/google_eengine/yvynation/reflex_app/.venv`) — the two apps will drift on
Reflex and kaleido versions, and Yvynation's is pinned to a working kaleido 1.3.0 render
lane that we have no reason to inherit.

```bash
cd /server/naturametrics
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

`.venv/` is gitignored.

## 3. `requirements.txt` (planned)

Pinned where the version matters, floating where it does not:

```
# Core
reflex==0.8.27              # same minor as Yvynation, so its component API matches
python-dotenv==1.0.0

# Earth Engine
earthengine-api>=1.7.4
google-auth>=2.27.0
google-auth-oauthlib>=1.2.1

# Data
pandas>=2.2.0
numpy>=2.0.0

# Viz
plotly>=6.1.1

# Geospatial (runtime)
shapely>=2.0.2
pyproj>=3.6.0

# Utilities
requests>=2.31.0
pydantic>=2.5.0
```

**Deliberately absent:** `folium` (the map is Leaflet-native — [02](02-architecture.md) §3),
`kaleido`/`matplotlib`/`seaborn` (chart export is client-side via Plotly
`toImage` — see [11-exports.md](11-exports.md) §4; Yvynation's server-side render lane is
the most fragile part of its deployment and there is no reason to inherit it), `geopandas` (heavy; needed only by the offline prep scripts).

`scripts/` has its own optional extras, installed only when preparing data:

```
# requirements-scripts.txt
geopandas>=0.14.0
openpyxl>=3.1.0     # for the IFN .xlsx products
```

## 4. Environment variables

`.env` at the repo root (gitignored); `.env.example` committed.

| Variable | Purpose | Default |
|---|---|---|
| `GCP_PROJECT_ID` | EE project. **Required** since the high-volume endpoint migration | `ee-leandromet` (shared with Yvynation — decision D5) |
| `EE_SERVICE_ACCOUNT_JSON` | Path to a service-account key (auth method 3) | unset |
| `EE_PRIVATE_KEY`, `EE_SERVICE_ACCOUNT_EMAIL`, `EE_PRIVATE_KEY_ID`, `EE_CLIENT_ID` | Env-var service account (auth method 1, for deployment) | unset |
| `NM_EE_CONCURRENCY` | EE thread-pool size | 64 (partner tier) |
| `NM_EE_TIER` | `partner` \| `contributor` — sizes the concurrency profile | `partner` |
| `NM_SPOT_ENABLED` | Feature flag for the licence-gated SPOT layers | `false` |
| `NM_HANSEN_TREECOVER_THRESHOLD` | Default tree-cover % defining Hansen forest | `30` |
| `NM_IFN_CATALOG` | Path to the derived IFN catalogue | `data/ifn_points.csv` |
| `REFLEX_DB_URL` | Reflex state DB | `sqlite:///reflex.db` |
| `REFLEX_LOG_LEVEL` | | `info` |
| `PORT` / `BACKEND_PORT` | Frontend / backend ports | see §5 |

Locally, `GCP_PROJECT_ID` + existing ADC is enough; no service-account file needed.

## 5. Ports

Chosen to avoid every port already in use across this machine's projects — Yvynation runs
3000/8000, `terra_web` occupies 3000/3003/3004/3005, and **8010 was already held by
another local Python process** when this was set up:

| Service | Port |
|---|---|
| Reflex frontend | **3010** |
| Reflex backend | **8011** |

Set in `rxconfig.py`, overridable by `PORT` / `BACKEND_PORT` (Cloud Run injects `PORT`).

## 6. Commands

```bash
source .venv/bin/activate

reflex run                      # dev server, hot reload
reflex run --env prod           # production build locally
reflex db init                  # first run only

# Offline data preparation (not part of the app runtime)
python scripts/fetch_ifn.py --list                 # show available UFs and datasets
python scripts/fetch_ifn.py --uf AC --uf GO        # download a couple of states
python scripts/fetch_ifn.py --all                  # all 27 UFs
python scripts/fetch_ifn.py --all --build-catalog  # download + build data/ifn_points.csv
python scripts/fetch_ifn.py --catalog-only --all   # rebuild the catalogue, download nothing
```

## 7. Repo conventions

- Git root is `/server/naturametrics` itself (unlike `terra_web`, where git lives one level
  down). Branch `main`. **No remote configured yet** — add one before relying on pushes.
- **Do not commit or push without being asked.**
- Commit messages: `feat:` / `fix:` / `docs:` / `chore:`, imperative mood. Portuguese or
  English is fine — pick one and stay consistent (the sibling `terra_web` uses Portuguese).
- Large files never enter git — see [data/README.md](../data/README.md) and constraint C3.

## 8. Reference app

Yvynation lives at `/home/leandromb/google_eengine/yvynation/reflex_app/`. Useful reading
while implementing:

| Path | For |
|---|---|
| `yvynation/utils/ee_service.py` | The auth ladder — port this |
| `yvynation/utils/ee_concurrency.py` | EE executor + `tune_ee_connection_pool()` — port the EE half |
| `yvynation/utils/ee_layers.py` | `_cached_get_map_id` + tile cache |
| `yvynation/utils/deforestation_timeline.py` | Validated DSV class semantics, `_reduce_stacked` |
| `yvynation/utils/hansen_analysis.py` | GFC handling |
| `yvynation/config/config.py` | MapBiomas + Hansen + aux dataset tables |
| `yvynation/state/` | The mixin composition pattern |
| `docs/BATCH_CONCURRENCY.md` | Why the concurrency module is shaped the way it is |
| `CLOUD_RUN_DEPLOYMENT.md` | For the eventual deployment phase |

It is a reference, not a dependency: **nothing in Naturametrics imports from Yvynation.**
Ported code is copied and adapted, so the two can diverge freely.
