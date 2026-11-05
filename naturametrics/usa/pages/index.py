"""The ``/usa`` workspace: map plus layer controls plus results."""

from __future__ import annotations

import reflex as rx

from ...components.map import leaflet_map
from ...components.panel_kit import workspace_with_sheet
from ...components.quickstart import quickstart_card
from ..components.layer_panel import layer_panel
from ..components.layout import ACCENT, shell
from ..components.map_legend import map_legend
from ..components.results import results_drawer
from ..state import USState as S


def map_pane() -> rx.Component:
    return rx.box(
        leaflet_map(
            id="nm-usa-map",
            center=S.map_center,
            zoom=S.map_zoom,
            bounds=S.map_bounds,
            swipe=S.compare_on,
            layers=S.map_layers,
            overlays=S.map_overlays,
            vectors=S.map_vectors,
            fit_bounds=S.fit_bounds,
            on_map_click=S.set_study_point,
            on_layer_meta=S.on_gbif_layer_meta,
            width="100%",
            height="100%",
        ),
        map_legend(),
        # desktop_from=3: like the Brazil page, the bottom sheet stays up to "lg".
        quickstart_card(S, accent=ACCENT, desktop_from=3),
        width="100%", height="100%",
        # Leaflet needs a positioned, sized container or it renders one grey tile.
        position="absolute", top="0", left="0",
    )


def workspace_main() -> rx.Component:
    """One map and one flex column at every breakpoint, the Brazil page's arrangement: below
    desktop the controls and the results live in a draggable bottom sheet over the map; on
    desktop the results sit under it (``components/panel_kit.py``)."""
    return workspace_with_sheet(
        S, map_pane=map_pane(), results=results_drawer,
        panel_for_sheet=lambda: layer_panel(fill_height=False), accent=ACCENT)


def usa_index() -> rx.Component:
    return shell(sidebar=layer_panel(), main=workspace_main())
