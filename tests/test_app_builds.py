"""The page must compile.

Reflex validates event-handler signatures against what each component's trigger
can emit, and it does so while *building the page* — not at import time and not
when the handler runs. A mismatch therefore surfaces as
``EventHandlerArgTypeMismatchError`` inside the worker, which kills it. The
frontend still serves, so the symptom a user sees is a **grey map and a failed
WebSocket connection to the backend**, which looks nothing like a type error.

This test builds every page in-process, so that failure mode is caught here
instead of at runtime.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_index_page_builds():
    from naturametrics.pages.index import index
    component = index()
    assert component is not None


def test_app_module_imports_and_registers_pages():
    import naturametrics.naturametrics as app_module
    assert app_module.app is not None


def test_every_event_handler_signature_is_accepted():
    """Rendering forces Reflex to validate every on_* binding on the page."""
    from naturametrics.pages.index import index
    rendered = index().render()
    assert rendered


def test_state_composes():
    from naturametrics.state import AppState
    for required in ("map_layers", "buffer_overlays", "selected_radius",
                     "has_point", "analysis_running"):
        assert required in AppState.get_fields(), f"missing state var: {required}"


def test_basemap_is_seeded_before_any_backend_event():
    """The map must have something to draw on the first render.

    If ``map_layers`` starts empty, the map is a grey rectangle until the
    background ``initialise`` event completes — and if the backend is slow or
    down, permanently.
    """
    from naturametrics.state import AppState
    seeded = AppState.get_fields()["map_layers"].default_value()
    assert seeded, "map_layers must be seeded with a basemap"
    assert seeded[0]["id"].startswith("basemap:")
    assert seeded[0]["url"].startswith("http")
