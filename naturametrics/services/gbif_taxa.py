"""The GBIF backbone taxonomy — the cascading picker's data source.

Separate from services/gbif.py because it answers a different question against
a different endpoint with a completely different lifetime. Occurrences are
per-viewport, cached for minutes, and weigh megabytes; the backbone is global,
changes a handful of times a year, and one branch of it is a few kilobytes.
Mixing them would mean one cache TTL serving both, and the wrong one either way.

**This is the part that keeps the accordion free.** A faceted search UI that
asks the network on every keystroke and every dropdown open is the usual way
these get expensive — with the BigQuery plan it would have been a billed query
per interaction, which is why that plan carried a pre-built catalogue table and
a committed CSV. Against the REST API none of that is needed: the backbone
endpoints cost nothing, and a day-long in-process cache means each branch is
fetched once per deploy and answered from memory forever after. The occurrence
endpoint — the only one that moves real data — is touched only when points are
actually drawn.

Nothing here raises. A failed backbone lookup returns an empty list, and the
picker shows one fewer level rather than breaking the panel around it.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from ..config import gbif as gc
from ..config.settings import (
    GBIF_TAXA_CACHE_TTL_S,
    GBIF_TIMEOUT_CONNECT,
    GBIF_TIMEOUT_READ,
)
from .gbif import get_session

logger = logging.getLogger(__name__)

_TIMEOUT = (GBIF_TIMEOUT_CONNECT, GBIF_TIMEOUT_READ)

#: How many children one backbone node may return. Insecta has ~1000 families;
#: a picker listing more than this is unusable as a dropdown anyway, and the
#: name box is the right tool past that point.
_CHILDREN_LIMIT = 1000


@dataclass
class _Entry:
    value: Any
    stored_at: float

    def fresh(self) -> bool:
        return (time.time() - self.stored_at) < GBIF_TAXA_CACHE_TTL_S


_cache: dict[str, _Entry] = {}
_cache_lock = threading.Lock()


def _cached(key: str, produce) -> Any:
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and hit.fresh():
            return hit.value
    try:
        value = produce()
    except Exception as exc:  # noqa: BLE001
        logger.warning("GBIF backbone lookup %s failed: %s", key, exc)
        # Cached too, deliberately: without this a branch that is failing
        # upstream is re-requested on every single re-render of the panel,
        # turning one outage into a request storm. A day is too long to hold a
        # failure, though, so it is stored with a stale timestamp that expires
        # in a minute.
        with _cache_lock:
            _cache[key] = _Entry([], time.time() - GBIF_TAXA_CACHE_TTL_S + 60)
        return []
    with _cache_lock:
        _cache[key] = _Entry(value, time.time())
    return value


def _get(url: str, params: list[tuple[str, str]]) -> Any:
    r = get_session().get(url, params=params, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def children(key: int, rank: str | None = None) -> list[dict]:
    """Direct backbone children of ``key``, as ``{key, name, rank}``.

    ``rank`` filters the result to one rank. The backbone is not strictly
    rank-complete — some branches skip a level, so asking for the CLASS
    children of a phylum can legitimately return nothing while the phylum does
    have descendants. The caller (state/_gbif.py) treats an empty level as
    "skip this dropdown", not as an error.
    """
    cache_key = f"children:{key}:{rank or '*'}"

    def produce() -> list[dict]:
        payload = _get(gc.SPECIES_CHILDREN.format(key=key),
                       [("limit", str(_CHILDREN_LIMIT))])
        rows = []
        for r in payload.get("results", []):
            if rank and r.get("rank") != rank:
                continue
            name = r.get("canonicalName") or r.get("scientificName")
            if not name or not r.get("key"):
                continue
            rows.append({"key": r["key"], "name": name, "rank": r.get("rank", "")})
        # By name: GBIF returns children in backbone order, which is neither
        # alphabetical nor by abundance and reads as random in a dropdown.
        rows.sort(key=lambda r: r["name"])
        return rows

    return _cached(cache_key, produce)


def suggest(query: str, limit: int = 12) -> list[dict]:
    """Name autocomplete, restricted to the GBIF backbone.

    ``/species/suggest`` accepts a ``datasetKey`` but does not reliably honour
    it — a bare query returns hits from contributor checklists as well, whose
    keys are not valid ``taxonKey`` values for an occurrence search. The
    response is therefore filtered on ``BACKBONE_DATASET_KEY`` here rather than
    trusting the parameter, so every suggestion offered is one that will
    actually filter the map.
    """
    query = (query or "").strip()
    if len(query) < 3:
        # Below three characters the suggestion list is noise and the request
        # is wasted — the picker shows nothing until the query means something.
        return []

    cache_key = f"suggest:{query.lower()}:{limit}"

    def produce() -> list[dict]:
        payload = _get(gc.SPECIES_SUGGEST, [
            ("q", query),
            ("datasetKey", gc.BACKBONE_DATASET_KEY),
            ("limit", str(limit * 3)),  # room to filter, see below
        ])
        rows = []
        for r in payload:
            if r.get("datasetKey") and r["datasetKey"] != gc.BACKBONE_DATASET_KEY:
                continue
            name = r.get("canonicalName") or r.get("scientificName")
            if not name or not r.get("key"):
                continue
            rows.append({
                "key": r["key"],
                "name": name,
                "rank": r.get("rank", ""),
                # The higher taxon is what disambiguates the genus homonyms
                # GBIF is full of — three different Panthera-like names in the
                # same list are indistinguishable without it.
                "context": r.get("family") or r.get("order") or r.get("class")
                           or r.get("phylum") or r.get("kingdom") or "",
            })
            if len(rows) >= limit:
                break
        return rows

    return _cached(cache_key, produce)


def kingdom_options() -> list[dict]:
    """The eight backbone kingdoms. Hard-coded in config, not fetched — this
    is the one level that is genuinely fixed, and it saves a round-trip before
    the user has chosen anything."""
    return [{"key": k, "name": n, "rank": "KINGDOM"} for k, n in gc.KINGDOMS]


def detail(key: int) -> dict:
    """One backbone node, for turning a stored taxon_key back into a label
    (a shared or reloaded URL carries the key, not the name)."""
    def produce() -> dict:
        r = _get(gc.SPECIES_DETAIL.format(key=key), [])
        return {
            "key": r.get("key", key),
            "name": r.get("canonicalName") or r.get("scientificName") or str(key),
            "rank": r.get("rank", ""),
        }

    value = _cached(f"detail:{key}", produce)
    return value if isinstance(value, dict) else {"key": key, "name": str(key),
                                                  "rank": ""}


__all__ = ["children", "suggest", "kingdom_options", "detail"]
