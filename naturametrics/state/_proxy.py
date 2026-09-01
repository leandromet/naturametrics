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


def state_class(state):
    """The concrete state class behind ``self``, background task or not.

    Returning one event handler from another is written ``type(self).other(...)``
    throughout these mixins, and that is correct in an ordinary handler where
    ``self`` is the state instance. Inside ``@rx.event(background=True)`` it is
    not: Reflex hands the task a ``StateProxy``, so ``type(self)`` is
    ``StateProxy`` and the lookup fails with

        AttributeError: type object 'StateProxy' has no attribute 'choose_municipio'

    A mixin cannot simply name ``AppState`` either — ``state/__init__.py``
    imports the mixins, so the reference has to be resolved at call time rather
    than at import time. Unwrapping the proxy does that without an import and
    without the caller having to know which kind of handler it is in.

    **Never reach for the mixin class instead** (``SearchMixin.choose_municipio``).
    Reflex only materialises ``EventHandler`` objects on the concrete state; on
    the mixin the same name is still a plain function, so calling it invokes the
    coroutine function directly with the first argument bound to ``self`` — a
    ``TypeError`` about a missing argument, or worse, silence.
    """
    return type(getattr(state, "__wrapped__", state))
