"""The ``/canada`` workspace: map plus layer controls plus results."""

from __future__ import annotations

import reflex as rx

from ...components.map import leaflet_map
from ..components.layer_panel import layer_panel
from ..components.layout import shell
from ..components.map_legend import map_legend
from ..components.results import results_drawer
from ..state import CanadaState as S


def map_pane() -> rx.Component:
    return rx.box(
        leaflet_map(
            id="nm-canada-map",
            center=S.map_center,
            zoom=S.map_zoom,
            bounds=S.map_bounds,
            layers=S.map_layers,
            overlays=S.buffer_overlays,
            vectors=S.map_vectors,
            fit_bounds=S.fit_bounds,
            on_map_click=S.set_study_point,
            on_layer_meta=S.on_gbif_layer_meta,
            width="100%",
            height="100%",
        ),
        map_legend(),
        width="100%", height="100%",
        # Leaflet needs a positioned, sized container or it renders one grey tile.
        position="absolute", top="0", left="0",
    )


def workspace_main() -> rx.Component:
    """Map above, results below. Same fixed-height-on-mobile reasoning as the
    Brazil page: a flex-sized map inside a scrolling column collapses to zero
    and Leaflet then paints a single grey tile."""
    return rx.vstack(
        rx.box(
            map_pane(),
            width="100%",
            height=["52dvh", "52dvh", "56dvh", "auto"],
            min_height=["300px", "320px", "360px", "0"],
            flex=["0 0 auto", "0 0 auto", "0 0 auto", "1 1 auto"],
            position="relative",
        ),
        results_drawer(),
        width="100%",
        height=["auto", "auto", "auto", "100%"],
        spacing="0", align_items="stretch",
    )


def canada_index() -> rx.Component:
    return shell(sidebar=layer_panel(), main=workspace_main())
