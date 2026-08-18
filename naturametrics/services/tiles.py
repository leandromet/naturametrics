"""Earth Engine tile-URL minting and cache.

Naturametrics never generates map HTML (decision D1). It asks Earth Engine for a
tile-URL template and hands that to the browser, which then fetches tiles
directly from Google — the app server is not in the tile path. That is what makes
year-switching instant once a URL is warm.

The cache is Yvynation's ``_cached_get_map_id`` pattern with two additions it
lacks: a TTL (EE tile URLs carry a signed component and expire) and a bound on
size.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

from ..config.settings import TILE_CACHE_MAX_ENTRIES, TILE_CACHE_TTL_SECONDS
from .ee_client import get_ee

logger = logging.getLogger(__name__)

_cache: "OrderedDict[str, tuple[str, float]]" = OrderedDict()
_cache_lock = threading.Lock()
#: Guards against two threads minting the same key simultaneously — which the
#: fan-out design makes likely, not hypothetical.
_inflight: dict[str, threading.Event] = {}


def _cache_get(key: str) -> str | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        url, minted_at = entry
        if time.time() - minted_at > TILE_CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            logger.debug("Tile URL expired: %s", key)
            return None
        _cache.move_to_end(key)
        return url


def _cache_put(key: str, url: str) -> None:
    with _cache_lock:
        _cache[key] = (url, time.time())
        _cache.move_to_end(key)
        while len(_cache) > TILE_CACHE_MAX_ENTRIES:
            evicted, _ = _cache.popitem(last=False)
            logger.debug("Tile cache evicted: %s", evicted)


def get_tile_url(
    cache_key: str,
    image_fn: Callable[[], Any],
    vis_params: dict[str, Any],
) -> str | None:
    """Mint (or reuse) a tile-URL template for an Earth Engine image.

    Args:
        cache_key: Must encode everything that changes the pixels — collection
            version, year, band, date window, vis params. A key that is too
            coarse serves the wrong tiles from cache, which is a confusing bug
            because the map looks plausible.
        image_fn: Called only on a cache miss, so building the ``ee.Image`` costs
            nothing on a hit.
        vis_params: Passed to ``getMapId``.

    Returns:
        The XYZ URL template, or None if Earth Engine could not produce one.
    """
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Collapse duplicate concurrent requests for the same key.
    with _cache_lock:
        event = _inflight.get(cache_key)
        if event is None:
            event = threading.Event()
            _inflight[cache_key] = event
            leader = True
        else:
            leader = False

    if not leader:
        event.wait(timeout=60)
        return _cache_get(cache_key)

    try:
        get_ee()  # ensure initialisation
        image = image_fn()
        map_id = image.getMapId(vis_params)
        url = map_id["tile_fetcher"].url_format
        _cache_put(cache_key, url)
        logger.info("Minted tile URL: %s", cache_key)
        return url
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to mint tile URL %s: %s", cache_key, exc)
        return None
    finally:
        with _cache_lock:
            _inflight.pop(cache_key, None)
        event.set()


def invalidate(prefix: str = "") -> int:
    """Drop cached URLs whose key starts with ``prefix`` (all of them if empty)."""
    with _cache_lock:
        keys = [k for k in _cache if k.startswith(prefix)]
        for key in keys:
            _cache.pop(key, None)
    return len(keys)


def cache_stats() -> dict[str, int]:
    with _cache_lock:
        return {"entries": len(_cache), "inflight": len(_inflight)}
