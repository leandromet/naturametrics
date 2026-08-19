# 13 — Abuse control

**Why this exists.** Every Reflex event handler is an unauthenticated public RPC by
design — true of this app from the start, and true of Yvynation too. That was an
acceptable risk while the only expensive path required clicking through the IFN grid or
picking a broad filter by hand. It stopped being acceptable the moment
`services/user_points.py` shipped: pasting a few thousand coordinates and pressing
"Baixar análise completa" costs the same ~17 minutes of Earth Engine compute (land-cover
history + vegetation age + the change mask, doc/11-exports.md) as the largest hand-built
selection, with no map interaction at all — trivial to script and loop. This module is
the response, written up during the pre-public-repo security audit.

Two independent layers, in the order they run:

1. **The friction step** (`components/exports.py`, `state/_export.py
   request_selection_download`) — a UI-only "are you sure" in front of any export that
   includes buffers. It shows the same cost estimate already computed for the panel
   (`services.exports.buffer_estimate_message`) and requires a second click. This
   deters an accidental or reflexive click; it deters nothing scripted, since a script
   calling `download_selection` directly over the WebSocket skips it entirely — which is
   exactly why it is not the enforcement.
2. **`services/abuse_control.py`** — the actual enforcement, checked server-side inside
   `download_selection` regardless of how it was reached.

---

## 1. The bucket

`gs://naturametrics-abuse-control` — created for this specifically, **not** shared with
Yvynation's own bucket (that one holds export files and has no rate-limiting or logging
logic in it at all; see the audit notes below). Reasons a bucket rather than in-process
state:

- **Cross-instance.** Cloud Run runs more than one instance under load, and an
  in-process counter would let a script spread requests across instances and never see
  a limit.
- **Survives a restart.** A deploy or a crashed instance does not reset anyone's
  cooldown or count.

Configuration (`config/settings.py`):

| Setting | Default | Meaning |
|---|---|---|
| `NM_ABUSE_BUCKET` | `naturametrics-abuse-control` | Bucket name |
| `NM_ABUSE_SESSION_COOLDOWN_S` | `300` | Minimum time between one browser tab's bulk exports |
| `NM_ABUSE_IP_MAX_PER_WINDOW` | `3` | Bulk exports one IP may start per window |
| `NM_ABUSE_IP_WINDOW_S` | `3600` | The window, in seconds |

Bucket properties (set once, at creation — not reproduced by app code):

- **Region:** `us-west1`, matching the Cloud Run service.
- **Uniform bucket-level access + public access prevention enforced.** Nobody reaches
  this bucket except through IAM; there is no signed-URL or object-ACL path in or out.
- **IAM:** `roles/storage.objectAdmin`, scoped to the bucket, granted to the Cloud Run
  runtime service account only (the same identity `doc/12-deployment.md` calls
  `<RUNTIME_SERVICE_ACCOUNT>`).
- **Lifecycle rule:** delete any object after 90 days. Nothing in this module manages
  retention itself — old rate-limit and log objects age out on their own.

## 2. What gets checked, and how

Two keys, both read-modify-write against a small JSON object with an
`if_generation_match` compare-and-swap (a handful of retries on a lost race — rare,
since it only happens under truly concurrent requests from the *same* key):

- **Session cooldown** — `cooldown/{client_token}.json`, `{"last_at": <epoch seconds>}`.
  Keyed on the Reflex **client token** (`self.router.session.client_token`), not the
  session id: the client token is stable across reconnects *and page reloads* for the
  same browser tab, so refreshing the page does not reset the cooldown the way an
  in-memory session field would have.
- **IP rate limit** — `ratelimit/{ip}.json`, `{"count": int, "window_start": <epoch
  seconds>}`. Keyed on `self.router.session.client_ip` — Reflex already unrolls
  `X-Forwarded-For` into this field correctly for a service sitting behind Cloud Run's
  proxy (`reflex/app.py`'s socket-connect handler), so no custom middleware was needed
  to get the real client address.

**Both fail open on any bucket error**, logged as a warning, not raised. A rate limiter
that takes the app down during a GCS hiccup is a worse bug than the abuse it exists to
catch — the friction step above still slows a human down even if this backstop is
briefly unavailable.

## 3. Logging

Every check — allowed or refused — writes one immutable JSON object to
`logs/{date}/{time}-{uuid}.json`:

```json
{
  "timestamp": "2026-08-19T23:14:33.86Z",
  "ip": "203.0.113.5",
  "client_token": "…",
  "session_id": "…",
  "action": "bulk_export",
  "outcome": "allowed",
  "detail": {"n_points": 1240, "radii": [1.0, 10.0]}
}
```

The IP is stored **in plain text** on purpose. The point of logging by IP is that the
app owner can read it back later to see who is hitting the limits and, if it comes to
that, block an address at the network level — the bucket is private (§1), so hashing it
here would only hide it from the one person it is for. One object per event rather than
appending to a shared log file: GCS has no atomic append, and a unique object name per
event sidesteps the concurrent-write problem entirely instead of needing to solve it.

To read the log:

```bash
gcloud storage cat gs://naturametrics-abuse-control/logs/2026-08-19/*.json
```

## 4. What was checked before building this (Yvynation)

Before writing a bucket-backed limiter, Yvynation was checked for one to reuse. It does
not have one: its own bucket holds export ZIPs only (read-only from the app's side —
Earth Engine's own export tasks write to it, the app never does), and grepping its
`state/`, `pages/` and `components/` trees for rate-limiting, IP extraction or a
confirm-before-expensive-action UI pattern turned up nothing. Everything in this module
was written for Naturametrics specifically, on a bucket of its own — sharing Yvynation's
bucket was considered and dropped once it was clear there was no existing mechanism in
it to extend, and a dedicated bucket costs a few objects' worth of storage either way.
