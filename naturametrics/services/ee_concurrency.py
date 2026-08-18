"""Earth Engine concurrency budget.

The EE half of Yvynation's ``utils/ee_concurrency.py``. Its render lanes,
territory lanes and pool meters belong to a batch pipeline we do not have; what
transfers is the sized request pool and — critically — the HTTP connection-pool
fix.

**Why this matters here.** Under the Partner tier (~360 M EECU-s/month, up to
60 000 simultaneous requests) Earth Engine is not the scarce resource; wall-clock
latency is. The design in doc/06-ee-layers.md §5b therefore fans requests out
widely and prefetches speculatively. That only works if the client can actually
hold many connections open — see :func:`tune_ee_connection_pool`.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from ..config.settings import EE_CONCURRENCY, EE_TIER

logger = logging.getLogger(__name__)

_ee_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()
_pool_tuned = False


def get_ee_executor() -> ThreadPoolExecutor:
    """The shared pool for Earth Engine requests.

    ``getInfo()`` is network-bound and releases the GIL, so threads are cheap
    here. A sized executor also queues everything past the Nth submission, which
    is the bounding we want — and unlike an asyncio semaphore it carries no
    event-loop affinity, so the same pool is reusable across Reflex background
    tasks.
    """
    global _ee_executor
    if _ee_executor is None:
        with _executor_lock:
            if _ee_executor is None:
                _ee_executor = ThreadPoolExecutor(
                    max_workers=EE_CONCURRENCY, thread_name_prefix="nm-ee"
                )
                logger.info(
                    "Earth Engine executor: %s workers (tier=%s)",
                    EE_CONCURRENCY, EE_TIER,
                )
    return _ee_executor


def tune_ee_connection_pool() -> bool:
    """Widen Earth Engine's HTTP connection pool to match the request budget.

    ``ee.data`` issues every Cloud API call through one shared
    ``requests.Session`` carrying urllib3's stock adapter, which caps the pool at
    **10 connections per host** — far below :data:`EE_CONCURRENCY`. Past the cap
    urllib3 does not block: it opens a throwaway connection, pays a fresh TLS
    handshake, discards it, and logs "Connection pool is full" for every call.
    Correct, but it turns the extra parallelism into handshake overhead.

    Without this, every fan-out and prefetch in this codebase underperforms for a
    reason that does not show up anywhere obvious. Called automatically from
    ``ee_client._post_init``.

    Returns:
        True when the pool was resized. Every failure mode is non-fatal — this
        reaches into ``ee.data`` internals, and the app is still correct on the
        default pool, just slower.
    """
    global _pool_tuned
    if _pool_tuned:
        return True

    try:
        from ee import data as ee_data
        from requests.adapters import HTTPAdapter

        session = getattr(ee_data._get_state(), "requests_session", None)
        if session is None:
            logger.debug("EE session not available yet — pool left at default")
            return False

        # Headroom over the worker count: redirects and token refreshes can
        # briefly hold a second connection while a call is in flight.
        size = EE_CONCURRENCY + 4
        # max_retries=0 — retries belong in our own wrapper, where they can log
        # and give up gracefully instead of silently blocking a worker.
        adapter = HTTPAdapter(pool_connections=size, pool_maxsize=size, max_retries=0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _pool_tuned = True
        logger.info("Earth Engine HTTP pool resized to %s connections", size)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Could not resize the Earth Engine HTTP pool (%s) — continuing on the "
            "default 10-connection pool; fan-out will be slower than designed", exc
        )
        return False


def describe_budget() -> str:
    """One-line summary for startup logs."""
    return (
        f"EE tier={EE_TIER} concurrency={EE_CONCURRENCY} "
        f"pool_tuned={_pool_tuned}"
    )
