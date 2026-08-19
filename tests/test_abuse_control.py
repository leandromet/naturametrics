"""services/abuse_control.py — rate limiting and access logging for the
Earth Engine-heavy bulk export.

Pure-logic tests run always; anything that reads or writes the live bucket is
marked ``gcs`` and skipped without credentials, following the same convention
test_exports.py/test_vegetation_age.py already use for ``ee``.
"""

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services import abuse_control as ac  # noqa: E402


# --------------------------------------------------------------------------- #
# Pure logic — no bucket
# --------------------------------------------------------------------------- #

def test_safe_key_neutralises_unsafe_characters():
    assert ac._safe_key("203.0.113.5") == "203.0.113.5"
    assert " " not in ac._safe_key("has spaces")
    assert "/" not in ac._safe_key("a/b/../c")


def test_safe_key_of_empty_string_is_never_empty():
    """An empty object-name component would either error or, worse, collide
    every caller onto the same blob — 'unknown' is a deliberate, visible
    placeholder, not silent data loss."""
    assert ac._safe_key("") == "unknown"


def test_checks_return_allowed_for_an_empty_identity():
    """No IP/token to key on (e.g. a bare state object in a test) must not
    block — there is nothing to rate-limit against, so refusing would be
    refusing everyone identically, which is not a rate limit."""
    ok, reason = ac.check_session_cooldown("")
    assert ok is True and reason == ""
    ok, reason = ac.check_ip_rate_limit("")
    assert ok is True and reason == ""


def test_checks_fail_open_when_the_bucket_is_unreachable(monkeypatch):
    """A rate limiter that takes the app down during a GCS hiccup is a worse
    bug than the abuse it exists to catch."""
    def _boom():
        raise RuntimeError("bucket unreachable")
    monkeypatch.setattr(ac, "_get_bucket", _boom)

    ok, reason = ac.check_session_cooldown("some-token")
    assert ok is True and reason == ""
    ok, reason = ac.check_ip_rate_limit("203.0.113.5")
    assert ok is True and reason == ""

    # Logging must not raise either — it is best-effort by contract.
    ac.log_event(ip="203.0.113.5", client_token="t", session_id="s",
                action="bulk_export", outcome="allowed")


# --------------------------------------------------------------------------- #
# Live bucket
# --------------------------------------------------------------------------- #

@pytest.fixture
def bucket_ready():
    try:
        bucket = ac._get_bucket()
        # A cheap call that actually exercises the credentials, not just
        # client construction — Client() succeeds even with no valid auth.
        bucket.exists()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Abuse-control bucket unavailable: {exc}")
    return bucket


@pytest.mark.gcs
def test_session_cooldown_blocks_a_second_call_and_then_expires(bucket_ready, monkeypatch):
    monkeypatch.setattr("naturametrics.config.settings.ABUSE_SESSION_COOLDOWN_S", 1)
    monkeypatch.setattr(ac, "ABUSE_SESSION_COOLDOWN_S", 1)
    token = f"test-{uuid.uuid4().hex[:8]}"
    try:
        ok, _ = ac.check_session_cooldown(token)
        assert ok is True
        ok, reason = ac.check_session_cooldown(token)
        assert ok is False and reason

        import time
        time.sleep(1.1)
        ok, _ = ac.check_session_cooldown(token)
        assert ok is True
    finally:
        bucket_ready.blob(f"cooldown/{ac._safe_key(token)}.json").delete()


@pytest.mark.gcs
def test_ip_rate_limit_allows_exactly_the_configured_max(bucket_ready, monkeypatch):
    monkeypatch.setattr(ac, "ABUSE_IP_MAX_PER_WINDOW", 2)
    monkeypatch.setattr(ac, "ABUSE_IP_WINDOW_S", 3600)
    ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"
    try:
        assert ac.check_ip_rate_limit(ip)[0] is True
        assert ac.check_ip_rate_limit(ip)[0] is True
        ok, reason = ac.check_ip_rate_limit(ip)
        assert ok is False
        assert "2" in reason  # names the configured limit, not a bare refusal
    finally:
        bucket_ready.blob(f"ratelimit/{ac._safe_key(ip)}.json").delete()


@pytest.mark.gcs
def test_log_event_writes_a_readable_record_with_plaintext_ip(bucket_ready):
    """The IP is deliberately not hashed — see the module docstring: the point
    of "log ... by ip" is that the app owner can read it back, and the bucket
    is private."""
    import json

    ip = "203.0.113.99"
    ac.log_event(ip=ip, client_token="tok-1", session_id="sess-1",
                action="bulk_export", outcome="allowed", detail={"n": 3})

    matches = [b for b in bucket_ready.list_blobs(prefix="logs/")
              if b.time_created and (
                  __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                  - b.time_created).total_seconds() < 30]
    assert matches, "no recent log object found"
    latest = max(matches, key=lambda b: b.time_created)
    payload = json.loads(latest.download_as_bytes())
    assert payload["ip"] == ip
    assert payload["action"] == "bulk_export"
    latest.delete()
