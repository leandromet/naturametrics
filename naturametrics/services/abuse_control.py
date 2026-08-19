"""Rate limiting and access logging for the Earth Engine-heavy bulk export.

Backed by a dedicated GCS bucket (config.settings.ABUSE_BUCKET) because Cloud
Run can and does run more than one instance, and in-process state does not
coordinate across them — a per-process counter would let a script spread its
requests across instances and never see a limit at all.

Two independent checks, both gating ``download_selection`` in state/_export.py:

* :func:`check_session_cooldown` — one browser tab may not start a second bulk
  export within :data:`~naturametrics.config.settings.ABUSE_SESSION_COOLDOWN_S`.
  Keyed on the Reflex *client token* (stable across reconnects and page
  reloads), not the session id, specifically so a refresh cannot reset it.
* :func:`check_ip_rate_limit` — one IP address may not start more than
  :data:`~naturametrics.config.settings.ABUSE_IP_MAX_PER_WINDOW` bulk exports
  inside :data:`~naturametrics.config.settings.ABUSE_IP_WINDOW_S`. This is the
  one that actually matters against a script: it catches many sessions or many
  reloads from the same address, which the cooldown alone cannot.

Both fail **open** on a bucket error — logged, not raised. A rate limiter that
takes the app down when GCS hiccups is a worse bug than the abuse it exists to
catch, and the friction step in the UI (components/exports.py) still slows a
human down even if this backstop is briefly unavailable.

Every check — allowed or refused — is also written to :func:`log_event` as one
small, immutable JSON object, named so a later listing sorts chronologically.
The bucket's own lifecycle rule deletes these after 90 days; nothing in this
module needs to.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config.settings import (
    ABUSE_BUCKET, ABUSE_IP_MAX_PER_WINDOW, ABUSE_IP_WINDOW_S,
    ABUSE_SESSION_COOLDOWN_S,
)

logger = logging.getLogger(__name__)

_bucket = None

#: GCS object names accept almost any UTF-8, but keeping rate-limit keys to a
#: predictable, safe subset makes the bucket listable/greppable by a human —
#: this is meant to be inspected, not just machine-read.
_UNSAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _safe_key(raw: str) -> str:
    return _UNSAFE_KEY_CHARS.sub("_", raw) or "unknown"


def _get_bucket():
    global _bucket
    if _bucket is not None:
        return _bucket
    from google.cloud import storage
    _bucket = storage.Client().bucket(ABUSE_BUCKET)
    return _bucket


def _read_json(blob) -> tuple[dict[str, Any] | None, int | None]:
    """(payload, generation) — (None, None) if the object does not exist."""
    if not blob.exists():
        return None, None
    blob.reload()
    return json.loads(blob.download_as_bytes()), blob.generation


def _cas_write(blob, generation: int | None, payload: dict[str, Any]) -> bool:
    """Compare-and-swap write. True on success, False on a lost race."""
    from google.api_core.exceptions import PreconditionFailed
    body = json.dumps(payload).encode("utf-8")
    try:
        if generation is None:
            blob.upload_from_string(body, content_type="application/json",
                                    if_generation_match=0)
        else:
            blob.upload_from_string(body, content_type="application/json",
                                    if_generation_match=generation)
        return True
    except PreconditionFailed:
        return False


def check_session_cooldown(client_token: str) -> tuple[bool, str]:
    """True if this browser tab may start a bulk export now.

    Not a security boundary by itself — a client token is client-supplied and
    a determined script can mint a new one per request, which is exactly why
    :func:`check_ip_rate_limit` exists as the check that cannot be sidestepped
    that cheaply.
    """
    if not client_token:
        return True, ""
    try:
        blob = _get_bucket().blob(f"cooldown/{_safe_key(client_token)}.json")
        existing, generation = _read_json(blob)
        now = time.time()
        if existing and now - existing.get("last_at", 0) < ABUSE_SESSION_COOLDOWN_S:
            wait_s = int(ABUSE_SESSION_COOLDOWN_S - (now - existing["last_at"]))
            return False, (
                f"Espere cerca de {max(1, wait_s // 60) if wait_s >= 60 else wait_s} "
                f"{'min' if wait_s >= 60 else 's'} antes de baixar outra planilha "
                f"completa nesta aba."
            )
        # Best-effort: a lost race here just means two exports 300 s apart
        # instead of exactly one, never a security gap — the IP check covers
        # the case that matters.
        _cas_write(blob, generation, {"last_at": now})
        return True, ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Session cooldown check failed open: %s", exc)
        return True, ""


def check_ip_rate_limit(ip: str) -> tuple[bool, str]:
    """True if this IP address may start a bulk export now."""
    if not ip:
        return True, ""
    try:
        blob = _get_bucket().blob(f"ratelimit/{_safe_key(ip)}.json")
        now = time.time()
        # A handful of retries against concurrent writers from the SAME IP —
        # rare, but a lost compare-and-swap must not silently grant an extra
        # request past the limit.
        for _attempt in range(3):
            existing, generation = _read_json(blob)
            if existing and now - existing.get("window_start", 0) < ABUSE_IP_WINDOW_S:
                count, window_start = existing["count"], existing["window_start"]
            else:
                count, window_start = 0, now
            if count >= ABUSE_IP_MAX_PER_WINDOW:
                wait_min = int((window_start + ABUSE_IP_WINDOW_S - now) / 60) + 1
                return False, (
                    f"Limite de {ABUSE_IP_MAX_PER_WINDOW} planilhas completas por "
                    f"hora para este endereço. Tente novamente em cerca de "
                    f"{wait_min} min, ou reduza a seleção."
                )
            if _cas_write(blob, generation, {"count": count + 1,
                                             "window_start": window_start}):
                return True, ""
        # Lost the race three times in a row: an unlucky user, not an attack.
        return True, ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("IP rate limit check failed open: %s", exc)
        return True, ""


def log_event(*, ip: str, client_token: str, session_id: str, action: str,
              outcome: str, detail: dict[str, Any] | None = None) -> None:
    """One immutable JSON object per event. Best-effort — never raises.

    The IP is stored in plain text on purpose: the point of "log ... by ip" is
    that the app owner can read it back later to see who is hitting the
    limits, and the bucket itself is private (public access prevention is on,
    IAM is scoped to the Cloud Run runtime service account plus the project's
    own owners/editors) — hashing it here would only hide it from the one
    person it is for.
    """
    try:
        now = datetime.now(timezone.utc)
        name = (f"logs/{now:%Y-%m-%d}/{now:%H%M%S}-{uuid.uuid4().hex[:8]}.json")
        payload = {
            "timestamp": now.isoformat(),
            "ip": ip,
            "client_token": client_token,
            "session_id": session_id,
            "action": action,
            "outcome": outcome,
            "detail": detail or {},
        }
        _get_bucket().blob(name).upload_from_string(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Abuse-control logging failed: %s", exc)
