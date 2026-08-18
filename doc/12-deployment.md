# 12 — Deployment (Cloud Run)

Decision **D10**: a new Cloud Run service named **`naturametrics`**, pointed at the same
Earth Engine project **`ee-leandromet`** — that is where the Partner-tier grant lives
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
region         southamerica-east1     # closest to the data and the users
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

## 3. Earth Engine credentials

**Cloud Run has no ADC file**, so the container must use auth method 1 of
`services/ee_client.py` — `EE_PRIVATE_KEY` + `EE_SERVICE_ACCOUNT_EMAIL`. This path is
written and unit-covered but has **not yet been exercised against a real service
account**; the local container test used a mounted ADC file instead. Exercise it before
trusting the first deploy.

```bash
export PROJECT_ID=ee-leandromet
export REGION=southamerica-east1
export SA=naturametrics@${PROJECT_ID}.iam.gserviceaccount.com

# 1. Service account
gcloud iam service-accounts create naturametrics \
  --display-name="Naturametrics Cloud Run" --project=$PROJECT_ID

# 2. Register it with Earth Engine — REQUIRED, and the step most easily missed.
#    A service account that merely authenticates against ee-leandromet is not the
#    same as one registered to use it; without this every EE call 403s.
#    https://console.cloud.google.com/earth-engine  →  Register service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" --role="roles/earthengine.writer"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" --role="roles/serviceusage.serviceUsageConsumer"

# 3. Key → Secret Manager (never into the image or the repo)
gcloud iam service-accounts keys create /tmp/nm-key.json --iam-account=$SA
python3 - <<'PY' > /tmp/nm-private-key.txt
import json; print(json.load(open('/tmp/nm-key.json'))['private_key'], end='')
PY
gcloud secrets create nm-ee-private-key --data-file=/tmp/nm-private-key.txt
shred -u /tmp/nm-key.json /tmp/nm-private-key.txt

gcloud secrets add-iam-policy-binding nm-ee-private-key \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
```

`ee_client._init_from_env_service_account` replaces literal `\n` with real newlines, so
the key survives a Secret Manager round-trip either way.

---

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
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},NM_EE_TIER=partner,NM_EE_CONCURRENCY=64,NM_BASEMAP=esri_imagery,NM_SPOT_ENABLED=false,EE_SERVICE_ACCOUNT_EMAIL=${SA}" \
  --set-secrets "EE_PRIVATE_KEY=nm-ee-private-key:latest"
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

The repo **has no git remote yet**; add it before any of this works.

```bash
gcloud builds triggers create github \
  --name=naturametrics-main \
  --repo-name=naturametrics --repo-owner=<github-user> \
  --branch-pattern='^main$' \
  --build-config=cloudbuild.yaml \
  --region=$REGION
```

Still undecided: whether `main` deploys straight to production or to a staging revision
with traffic migration. Until that is settled, deploy manually.

---

## 6. Rollback and tuning without a redeploy

```bash
# Earth Engine tier lapsed (Yvynation records the uplift expiring 2027-02-15)
gcloud run services update naturametrics --region $REGION \
  --set-env-vars NM_EE_TIER=contributor,NM_EE_CONCURRENCY=4

# Basemap, feature flags
gcloud run services update naturametrics --region $REGION \
  --set-env-vars NM_BASEMAP=google_maps
gcloud run services update naturametrics --region $REGION \
  --set-env-vars NM_SPOT_ENABLED=true        # only once the licence is granted

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
  -e PORT=8080 -e GCP_PROJECT_ID=ee-leandromet \
  -v ~/.config/earthengine:/root/.config/earthengine:ro \
  naturametrics:local
```

The ADC mount stands in for Secret Manager locally. It does **not** exercise the env-var
service-account path that Cloud Run actually uses — test that separately with a real key
before the first deploy.
