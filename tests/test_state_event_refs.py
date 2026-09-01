"""Cross-handler event references must resolve to real EventHandlers.

Returning one event handler from another is written ``type(self).other(...)``
throughout ``naturametrics/state``. That is correct in an ordinary handler,
where ``self`` is the state instance — and silently wrong in two ways that a
page build cannot catch, because both only fail when the handler actually runs:

1. **Inside ``@rx.event(background=True)``**, Reflex hands the task a
   ``StateProxy``, so ``type(self)`` is ``StateProxy`` and the attribute lookup
   raises ``AttributeError: type object 'StateProxy' has no attribute 'x'``.
   Use ``_proxy.state_class(self)``, which unwraps the proxy.

2. **Naming the mixin class** (``SearchMixin.choose_municipio(...)``) looks like
   the obvious way for a mixin to reach a sibling handler, but Reflex only
   materialises ``EventHandler`` objects on the concrete state — on the mixin
   the same name is still a plain function, so the call invokes the coroutine
   function with its first argument bound to ``self``: a ``TypeError`` about a
   missing argument, or worse, silence.

Both shipped at least once. Neither is visible to ``test_app_builds.py``, and
the runtime symptom is a dead worker (a grey map and a failed WebSocket), which
looks nothing like the cause. This test reads the source instead.
"""

import ast
import sys
from pathlib import Path

import pytest

STATE_DIR = Path(__file__).resolve().parent.parent / "naturametrics" / "state"
sys.path.insert(0, str(STATE_DIR.parent.parent))

MIXIN_FILES = sorted(STATE_DIR.glob("_*.py"))


def _is_background(fn: ast.AST) -> bool:
    """``@rx.event(background=True)`` on a function definition."""
    return any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "background"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in dec.keywords)
        for dec in getattr(fn, "decorator_list", [])
    )


def _handlers(path: Path):
    """Every method in every class in one mixin module, with its source."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for fn in cls.body:
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield source, cls, fn


@pytest.mark.parametrize("path", MIXIN_FILES, ids=lambda p: p.name)
def test_no_type_self_inside_background_handler(path: Path):
    """``type(self)`` is ``StateProxy`` in a background task — see case 1."""
    offenders = []
    for source, cls, fn in _handlers(path):
        if not _is_background(fn):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Attribute):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if segment.startswith("type(self)."):
                offenders.append(
                    f"{path.name}:{node.lineno} {cls.name}.{fn.name} -> {segment}"
                )
    assert not offenders, (
        "type(self) inside a background handler resolves to StateProxy. "
        "Use state_class(self) from naturametrics.state._proxy:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("path", MIXIN_FILES, ids=lambda p: p.name)
def test_no_handler_called_on_a_mixin_class(path: Path):
    """A mixin holds plain functions, not EventHandlers — see case 2."""
    offenders = []
    for source, cls, fn in _handlers(path):
        for node in ast.walk(fn):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            if isinstance(value, ast.Name) and value.id.endswith("Mixin"):
                segment = ast.get_source_segment(source, node) or ""
                offenders.append(
                    f"{path.name}:{node.lineno} {cls.name}.{fn.name} -> {segment}"
                )
    assert not offenders, (
        "Event handlers exist on the concrete state, not on the mixin. "
        "Use type(self) (ordinary handler) or state_class(self) (background):\n  "
        + "\n  ".join(offenders)
    )


def test_state_class_unwraps_a_state_proxy():
    """The helper the two rules above point at actually does the job."""
    from reflex.istate.proxy import StateProxy

    from naturametrics.state import AppState
    from naturametrics.state._proxy import state_class

    real = AppState(_reflex_internal_init=True)
    proxy = StateProxy(real)

    # The precise failure this helper exists to prevent.
    with pytest.raises(AttributeError):
        type(proxy).choose_municipio

    assert state_class(proxy) is AppState
    assert state_class(real) is AppState
    # And the unwrapped class really does carry EventHandlers.
    assert type(state_class(proxy).choose_municipio).__name__ == "EventHandler"
