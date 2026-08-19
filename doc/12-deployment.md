# 12 — Deployment (Cloud Run)

Decision **D10**: a new Cloud Run service named **`naturametrics`**, pointed at the same
Earth Engine project **`<GCP_PROJECT_ID>`** — that is where the Partner-tier grant lives
(**D5**), and a different project would silently drop to contributor limits.

Yvynation's `CLOUD_RUN_DEPLOYMENT.md` is the model. This image is deliberately much
lighter: no Chromium/kaleido (chart export is client-side) and no GDAL (shapely and
pyproj ship manylinux wheels; geopandas is only used by the offline scripts).

---

## 1. Verified locally

Built and run before writing any of this down:

| | |
|---|---|
| Image size | **1.63 GB** |
| Build | ✅ frontend production build baked in at image-build time |
| Cold start to serving | **~6–15 s** |
| First map tile painted | **0.23 s** |
| Earth Engine | ✅ 40 year tile URLs cached |
| Click → history chart | **3.71 s** |
| Idle memory | **~356 MB** |
| Console errors | 0 |

**~356 MB idle against a 4 GiB limit** leaves a very wide margin. The request path is
network-bound (`getInfo` waiting on Earth Engine), so 2 vCPU is the right shape; the
64-thread EE pool costs threads, not cores.

---

## 2. Service configuration

```
service        naturametrics
region         us-west1               # matches yvynation-reflex
cpu            2
memory         4Gi
concurrency    40                     # Reflex holds per-session state in-process
timeout        300s
min-instances  0                      # 1 if cold starts become annoying
max-instances  4
```

**Why `--concurrency 40` and not the default 80:** Reflex keeps per-session state in the
worker process, and each active session holds its analysis DataFrame. 40 concurrent
sessions at a few MB each is comfortable inside 4 GiB; 80 is closer to the edge than
there is any reason to be.

**Why `max-instances 4`:** the tile-URL cache is per-instance, so every extra instance
re-mints URLs Earth Engine has already produced for another. Scaling wide is cheap for
Cloud Run and slightly wasteful for us. Four is plenty for this workload.

---

## 3. Earth Engine credentials — none needed

> **Correction.** An earlier draft of this document claimed "Cloud Run has no ADC file,
> so the container must use `EE_PRIVATE_KEY`". **That is wrong.** Cloud Run exposes
> Application Default Credentials for the *attached service account* through the
> metadata server, which is auth method 2 in `services/ee_client.py` — the same path
> used locally. No key, no Secret Manager, no `EE_PRIVATE_KEY`.

The proof is next door: `yvynation-reflex` runs in this same project with **exactly one**
environment variable (`GCS_EXPORT_BUCKET`) and no Earth Engine credential of any kind.

So the whole credential setup reduces to **attaching a service account that Earth Engine
accepts**:

| Service account | Roles | Notes |
|---|---|---|
| `<RUNTIME_SERVICE_ACCOUNT>` | `artifactregistry.writer`, `run.admin`, `logging.logWriter`, `iam.serviceAccountUser`, `editor` | **Recommended.** Already the runtime identity of `yvynation-reflex`, so it is proven to reach Earth Engine, and it already carries every role a Cloud Build → Cloud Run pipeline needs. |
| `<LEGACY_SERVICE_ACCOUNT>` | `earthengine.admin`, `earthengine.viewer`, `editor` | Runtime identity of the older `yvynation` service. Explicit EE roles, but lacks the CI-specific roles. |

`EE_PRIVATE_KEY` / `EE_SERVICE_ACCOUNT_EMAIL` remain supported in `ee_client.py` and are
the right path for an identity that *cannot* be attached to the service — they are simply
not needed here.

**Also needed as of doc/13-abuse-control.md:** `roles/storage.objectAdmin`, scoped to
`gs://naturametrics-abuse-control` specifically (not project-wide), on whichever service
account is attached. Already granted on the current deployment; a fresh one needs:

```bash
gcloud storage buckets add-iam-policy-binding gs://naturametrics-abuse-control \
  --member="serviceAccount:<RUNTIME_SERVICE_ACCOUNT>" --role="roles/storage.objectAdmin"
```

## 4. Deploy

```bash
gcloud run deploy naturametrics \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --service-account $SA \
  --cpu 2 \
  --memory 4Gi \
  --concurrency 40 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 4 \
  --allow-unauthenticated \
  --cpu-boost \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},NM_EE_TIER=partner,NM_EE_CONCURRENCY=64,NM_BASEMAP=google_hybrid,NM_SPOT_ENABLED=true"
```

`--source .` uses `.gcloudignore` for the build context — which excludes `data/raw/` and
`data/cache/` while keeping `data/ifn_points.csv`, the one data file the image needs.

`PORT` is injected by Cloud Run and must not be set manually. The container runs
`reflex run --env prod --single-port`, so frontend and backend share it; the dev-time
3010/8011 split does not apply.

### Verify

```bash
URL=$(gcloud run services describe naturametrics --region $REGION --format='value(status.url)')
curl -sS -o /dev/null -w '%{http_code}\n' $URL
gcloud run services logs read naturametrics --region $REGION --limit 50
```

Open the URL and check: the map paints, the MapBiomas toggle reaches
*"Earth Engine pronto — 40 anos em cache"*, and a click produces the history chart. If the
map is grey and the console shows a failed WebSocket, the backend is failing — see
Troubleshooting.

---

## 5. Continuous deployment from `main`

Repo: **`github.com/leandromet/naturametrics`**, branch `main`.

### The trigger must use `cloudbuild.yaml`, not the Dockerfile config type

A trigger created with build config type **"Dockerfile"** generates an *inline* build with
`options: {}`. The moment such a trigger also has a build service account — which Cloud
Build now requires, since the legacy per-project Cloud Build SA is deprecated — it fails
before starting:

```
Failed to trigger build: invalid argument: if 'build.service_account' is specified,
the build must either (a) specify 'build.logs_bucket', (b) use the
REGIONAL_USER_OWNED_BUCKET build.options.default_logs_bucket_behavior option,
or (c) use either CLOUD_LOGGING_ONLY / NONE logging options
```

There is nowhere to put the logging option in a Dockerfile-type trigger. The fix is to
point the trigger at `cloudbuild.yaml`, which sets `options.logging: CLOUD_LOGGING_ONLY`.

```bash
# One-off: the Artifact Registry repo cloudbuild.yaml pushes to
gcloud artifacts repositories create naturametrics \
  --repository-format=docker --location=us-west1 --project=<GCP_PROJECT_ID>

# Repoint the existing trigger at the YAML
gcloud builds triggers update github naturametrics-trigg \
  --region=us-west1 --project=<GCP_PROJECT_ID> \
  --repo-owner=leandromet --repo-name=naturametrics \
  --branch-pattern='^main$' \
  --build-config=cloudbuild.yaml \
  --service-account=projects/<GCP_PROJECT_ID>/serviceAccounts/<RUNTIME_SERVICE_ACCOUNT>
```

The build service account needs `artifactregistry.writer`, `run.admin`,
`logging.logWriter` and `iam.serviceAccountUser` (to attach the runtime SA).
`<RUNTIME_SERVICE_ACCOUNT_PREFIX>@` already has all four — which is why it is the recommended choice
over `<LEGACY_SERVICE_ACCOUNT_PREFIX>@`, whose `editor` role covers most of it but not by design.

### Two failures worth remembering

**1. `Image ... not found` on the first real build.**
Cloud Build's top-level `images:` field pushes **after every step finishes**. A deploy
step inside the same build therefore references a tag that does not exist yet, and Cloud
Run fails the revision:

```
ERROR: (gcloud.run.deploy) Revision 'naturametrics-00001-wq5' is not ready and cannot
serve traffic. Image 'us-west1-docker.pkg.dev/.../naturametrics:e67f537' not found.
```

Fix: give the push its **own step** before deploy, and do not use `images:` at all.

**2. `Setting IAM Policy........warning`.**
`--allow-unauthenticated` makes gcloud set an `allUsers → roles/run.invoker` binding,
which needs `roles/run.admin`. A build service account with only `roles/editor` cannot do
it. Rather than widen the build SA, the flag is omitted from `cloudbuild.yaml` and public
access is granted **once**, out of band — it persists across revisions:

```bash
gcloud run services add-iam-policy-binding naturametrics \
  --region=us-west1 --member=allUsers --role=roles/run.invoker
```

**Registry note.** `cloudbuild.yaml` pushes to `gcr.io/<GCP_PROJECT_ID>/naturametrics`,
which already exists in this project — one less thing to create. A dedicated regional
Artifact Registry repo is cleaner long-term; switch `_IMAGE` if you make one.

### Run it

```bash
git push origin main                                   # trigger fires on push
gcloud builds list --region=us-west1 --limit=3         # watch
gcloud builds log <BUILD_ID> --region=us-west1
```

Still undecided: whether `main` deploys straight to production or to a staging revision
with traffic migration.

## 6. Rollback and tuning without a redeploy

```bash
# Earth Engine tier lapsed (Yvynation records the uplift expiring 2027-02-15)
gcloud run services update naturametrics --region $REGION \
  --set-env-vars NM_EE_TIER=contributor,NM_EE_CONCURRENCY=4

# Basemap, feature flags
gcloud run services update naturametrics --region $REGION \
  --set-env-vars NM_BASEMAP=google_maps
gcloud run services update naturametrics --region $REGION \
  --set-env-vars NM_SPOT_ENABLED=false       # if this account lacks the licence

# Previous revision
gcloud run services update-traffic naturametrics --region $REGION --to-revisions PREVIOUS=100
```

Nothing in the app *requires* Partner concurrency — dropping to `contributor` makes it
slower, not broken.

---

## 7. Troubleshooting

**Grey map, console shows a failed WebSocket to `_event/`.** The backend is not reachable.
Three known causes, in order of likelihood:

1. **The worker crashed at build time.** A Reflex event-handler signature mismatch kills
   the worker while the frontend keeps serving. The Dockerfile runs `index().render()` as
   a build-time smoke test precisely so this fails the build instead of the deploy.
2. **Earth Engine credentials are wrong**, so `initialize_earth_engine` raises at startup.
   Check the service account is *registered with Earth Engine*, not merely IAM-bound.
3. **Port mismatch.** Reflex builds the WebSocket URL from the backend port. This bit the
   local container test: running `-p 8090:8080` made the page load fine while the browser
   tried `ws://localhost:8080` and failed. On Cloud Run the runtime rewrites to
   `wss://<host>/_event` over HTTPS, so this is a local-testing trap rather than a
   production one — but it produces the identical symptom, so do not mis-map ports when
   testing the image.

**Slow cold start.** The frontend production build is baked into the image
(`reflex export --frontend-only` at build time). If cold starts regress, check that step
still runs — without it every cold start pays a multi-minute Vite build.

**SPOT layers disabled.** Expected until the *Brazil Forest Imagery Dataset 2008* licence
is accepted for **this** service account. `NM_SPOT_ENABLED=false` makes them fail closed
with an explanation rather than a traceback.

---

## 8. Local container testing

```bash
docker build -t naturametrics:local .

# Ports MUST match, or the WebSocket points at an unmapped port (§7.3).
docker run --rm -p 8080:8080 \
  -e PORT=8080 -e GCP_PROJECT_ID=<GCP_PROJECT_ID> \
  -v ~/.config/earthengine:/root/.config/earthengine:ro \
  naturametrics:local
```

The ADC mount stands in for Secret Manager locally. It does **not** exercise the env-var
service-account path that Cloud Run actually uses — test that separately with a real key
before the first deploy.
