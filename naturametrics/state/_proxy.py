"""Getting plain Python back out of Reflex state."""

from __future__ import annotations


def plain(value):
    """Strip Reflex's ``MutableProxy`` wrappers, recursively.

    Reflex wraps every mutable it hands out of state so it can detect writes, and
    the wrapper is transparent to ``isinstance`` — which is exactly what makes it
    dangerous here. ``dict(state_var)`` copies only the top level; the nested
    lists and dicts are still proxies, and the first thing that tries to
    *reconstruct* one of them blows up. ``dataclasses.asdict`` does precisely
    that (``type(obj)(...)``), so the failure surfaced deep inside provenance
    serialisation with a message about a constructor nobody wrote a call to.

    Anything crossing from state into a service gets flattened here, at the one
    boundary, rather than each service defending itself.
    """
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value
