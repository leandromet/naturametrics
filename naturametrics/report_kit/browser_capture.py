"""Chart capture in the browser (Naturametrics, Camposcope) — doc/14 §2.7.

The server sends each figure's JSON; the browser rasterises it with
``Plotly.toImage`` and posts every PNG back as its own socket event. Two
pieces live here because both apps need them identically:

* :func:`build_capture_script` — ONE script, no ``call_script`` callback of
  its own. Each ``call_script`` holds the page's event queue while its
  Promise is pending, and a rejected Promise never fires its callback, so N
  scripts would both freeze the page and risk a hung report. The app passes
  one pre-built callback per chart (``format_queue_events(...)`` output —
  the kit never imports Reflex).
* :class:`JobStore` — where the PNGs wait for the build task. Deliberately
  outside Reflex state: even ``_backend`` vars are pickled on every event.

Reflex caps an *incoming* socket message at ``REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE``
(1 000 000 bytes by default) and drops the connection silently beyond it, so
the script retries an oversized chart at 150 dpi, then scale 1, and gives up past
``max_chars`` rather than sending it.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Tuple

from . import images

MAX_CHARS = 900_000          # a data URL longer than this is never sent
MAX_PNG_BYTES = 3_000_000
MAX_PNG_SIDE = 4000


def _dumps(obj) -> str:
    try:  # plotly's encoder handles numpy arrays / dates inside figure dicts
        from plotly.utils import PlotlyJSONEncoder
        return json.dumps(obj, cls=PlotlyJSONEncoder, separators=(",", ":"))
    except ImportError:
        return json.dumps(obj, separators=(",", ":"), default=str)


def build_capture_script(figs: Mapping[str, dict], callbacks: Mapping[str, str],
                         opts: Mapping[str, dict], *, wait_ms: int = 8000,
                         max_chars: int = MAX_CHARS) -> str:
    """JavaScript that renders every figure and calls its callback with a
    ``data:image/png;base64,…`` URL, or ``""`` when it could not.

    ``figs`` — {key: prepared figure dict}; ``callbacks`` — {key: JS function
    source}; ``opts`` — {key: {"width", "height", "scale"}} from
    ``images.figure_opts(prepared, slot)``. Waits up to ``wait_ms`` for ``window.Plotly``
    (its bundle loads lazily with the first ``rx.plotly``).
    """
    keys = [k for k in figs if k in callbacks and k in opts]
    cb_src = ",".join(f"{json.dumps(k)}:{callbacks[k]}" for k in keys)
    return (
        "(async () => {"
        f"const figs = {_dumps({k: figs[k] for k in keys})};"
        f"const opts = {json.dumps({k: opts[k] for k in keys})};"
        f"const cbs = {{{cb_src}}};"
        f"const MAX = {int(max_chars)};"
        "const t0 = Date.now();"
        f"while (!window.Plotly && Date.now() - t0 < {int(wait_ms)}) "
        "{ await new Promise(r => setTimeout(r, 200)); }"
        "for (const key of Object.keys(figs)) {"
        "  let d = '';"
        "  if (window.Plotly) {"
        "    const o = opts[key];"
        "    try {"
        "      d = await window.Plotly.toImage(figs[key], {format: 'png', width: o.width,"
        "            height: o.height, scale: o.scale});"
        "      if (d.length > MAX) d = await window.Plotly.toImage(figs[key],"
        "            {format: 'png', width: o.width, height: o.height,"
        "             scale: o.scale * 150 / 220});"
        "      if (d.length > MAX) d = await window.Plotly.toImage(figs[key],"
        "            {format: 'png', width: o.width, height: o.height, scale: 1});"
        "      if (d.length > MAX) d = '';"
        "    } catch (e) { console.warn('report chart', key, e); d = ''; }"
        "  }"
        "  try { cbs[key](d); } catch (e) { console.warn('report callback', key, e); }"
        "}"
        "})();"
    )


@dataclass
class _Job:
    token: str
    expected: Tuple[str, ...]
    created: float = field(default_factory=time.monotonic)
    images: Dict[str, Optional[bytes]] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)


class JobStore:
    """Chart PNGs in flight between the browser and a report build.

    ``put`` validates before storing: the job's client token, the PNG data-URL
    prefix, a decoded size ≤ 3 MB and header dimensions ≤ 4000 px — the handler
    is a public RPC, so nothing arriving there is trusted. An empty payload is
    recorded as a failed chart (``None``), which the build turns into a
    "figure unavailable" placeholder instead of waiting for it.
    """

    def __init__(self, ttl_s: float = 600.0, max_jobs: int = 64):
        self.ttl_s = ttl_s
        self.max_jobs = max_jobs
        self._jobs: Dict[str, _Job] = {}
        self._lock = threading.Lock()

    def _prune(self) -> None:
        now = time.monotonic()
        for jid in [j for j, job in self._jobs.items() if now - job.created > self.ttl_s]:
            del self._jobs[jid]
        while len(self._jobs) > self.max_jobs:
            del self._jobs[next(iter(self._jobs))]

    def create(self, token: str, expected: Iterable[str]) -> str:
        job_id = secrets.token_urlsafe(12)
        with self._lock:
            self._prune()
            self._jobs[job_id] = _Job(token=str(token), expected=tuple(expected))
        return job_id

    def put(self, job_id: str, key: str, data_url: str, token: str) -> bool:
        """Store one chart. False (and nothing stored) for an unknown job, a
        foreign token or an unexpected key; a malformed image is recorded as a
        failure so the build does not wait for it."""
        with self._lock:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None or job.token != str(token) or key not in job.expected:
                return False
        png: Optional[bytes] = None
        error = ""
        if data_url:
            try:
                png = images.decode_data_url(data_url, MAX_PNG_BYTES)
                _, w, h = images.image_size(png)
                if w > MAX_PNG_SIDE or h > MAX_PNG_SIDE:
                    raise ValueError(f"{w}×{h} px exceeds {MAX_PNG_SIDE} px")
            except (ValueError, TypeError) as exc:
                png, error = None, str(exc)
        else:
            error = "browser could not render the chart"
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job.images[key] = png
            if error:
                job.errors[key] = error
        return True

    def progress(self, job_id: str) -> Tuple[int, int]:
        """(charts resolved, charts expected); (0, 0) for an unknown job."""
        with self._lock:
            job = self._jobs.get(job_id)
            return (len(job.images), len(job.expected)) if job else (0, 0)

    def done(self, job_id: str) -> bool:
        got, total = self.progress(job_id)
        return total == 0 or got >= total

    def take(self, job_id: str) -> Tuple[Dict[str, Optional[bytes]], Dict[str, str]]:
        """Remove the job and return ({key: png or None}, {key: error}); keys
        never received come back as None with a timeout error."""
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return {}, {}
        out = {k: job.images.get(k) for k in job.expected}
        errors = dict(job.errors)
        for k in job.expected:
            if k not in job.images:
                errors[k] = "timed out waiting for the browser"
        return out, errors


def wait_deadline_s(n_figures: int) -> float:
    """How long a build waits for the browser: 15 s + 2 s per figure."""
    return 15.0 + 2.0 * n_figures


#: The process-wide store both apps use.
STORE = JobStore()
