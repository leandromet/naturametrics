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
            layers=AppState.map_layers,
            overlays=AppState.buffer_overlays,
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
    """Map above, results drawer below. The map keeps the larger share."""
    return rx.vstack(
        rx.box(map_pane(), width="100%", flex="1", position="relative",
               min_height="0"),
        results_drawer(),
        width="100%", height="100%", spacing="0", align_items="stretch",
    )


def index() -> rx.Component:
    return shell(sidebar=layer_panel(), main=workspace_main())
