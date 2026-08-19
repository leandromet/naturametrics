"""The workspace: map plus layer controls.

Phase 0 delivers the map and the layer machinery. The click → buffer → analysis
loop is Phase 1; the map component already emits ``on_map_click``, so wiring it
is a state change, not a component change.
"""

from __future__ import annotations

import reflex as rx

from ..components.layout import shell
from ..components.layer_panel import layer_panel
from ..components.map import leaflet_map
from ..components.results import results_drawer
from ..state import AppState


def map_pane() -> rx.Component:
    return rx.box(
        leaflet_map(
            id="nm-map",
            center=AppState.map_center,
            zoom=AppState.map_zoom,
            bounds=AppState.map_bounds,
            swipe=AppState.compare_enabled,
            layers=AppState.map_layers,
            overlays=AppState.buffer_overlays,
            vectors=AppState.map_vectors,
            fit_bounds=AppState.fit_bounds,
            on_map_click=AppState.set_study_point,
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        # Leaflet needs a positioned, sized container or it renders one grey tile.
        position="absolute",
        top="0",
        left="0",
    )


def workspace_main() -> rx.Component:
    """Map above, results drawer below. The map keeps the larger share.

    On small screens the map gets an explicit viewport-fraction height instead
    of ``flex: 1``. Inside a scrolling column a flex-sized map collapses to zero
    height, and Leaflet then paints a single grey tile — the container has no
    size to lay tiles out in.
    """
    return rx.vstack(
        rx.box(
            map_pane(),
            width="100%",
            # A plain responsive list, not rx.cond(rx.breakpoints(...)): a
            # breakpoints object nested inside a conditional Var does not
            # resolve, and the prop silently falls through to min_height.
            height=["52dvh", "52dvh", "56dvh", "auto"],
            min_height=["300px", "320px", "360px", "0"],
            flex=["0 0 auto", "0 0 auto", "0 0 auto", "1 1 auto"],
            position="relative",
        ),
        results_drawer(),
        width="100%",
        height=["auto", "auto", "auto", "100%"],
        spacing="0",
        align_items="stretch",
    )


def index() -> rx.Component:
    return shell(sidebar=layer_panel(), main=workspace_main())
