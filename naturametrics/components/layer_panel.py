"""Sidebar controls for the map layers.

Phase 0 scope: basemap choice and the MapBiomas year/opacity controls. The year
slider is the acceptance test for decision D1 — moving it must repaint the layer
without the map viewport shifting.
"""

from __future__ import annotations

import reflex as rx

from ..config import datasets as ds
from ..config import mapbiomas as mb
from ..services import change_mask as cm
from ..state import AppState


def _section(title: str, *children) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="1", weight="bold", color_scheme="gray",
                style={"textTransform": "uppercase", "letterSpacing": "0.06em"}),
        *children,
        spacing="2",
        align_items="stretch",
        width="100%",
    )


def basemap_control() -> rx.Component:
    return _section(
        "Mapa base",
        rx.select(
            [ds.BASEMAPS[k]["label_pt"] for k in ds.BASEMAPS],
            value=rx.Var.create({k: v["label_pt"] for k, v in ds.BASEMAPS.items()})[
                AppState.basemap
            ],
            on_change=lambda label: AppState.set_basemap(
                rx.Var.create({v["label_pt"]: k for k, v in ds.BASEMAPS.items()})[label]
            ),
            width="100%",
        ),
    )


def mapbiomas_control() -> rx.Component:
    return _section(
        "Cobertura do solo",
        rx.hstack(
            rx.switch(
                checked=AppState.show_mapbiomas,
                on_change=AppState.toggle_mapbiomas,
            ),
            rx.text("MapBiomas 10.1", size="2"),
            rx.spacer(),
            rx.cond(
                AppState.layer_busy,
                rx.spinner(size="1"),
                rx.fragment(),
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        rx.cond(
            AppState.show_mapbiomas,
            rx.vstack(
                rx.hstack(
                    rx.text("Ano", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.mapbiomas_year.to_string(),
                             color_scheme="green", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=mb.MAPBIOMAS_YEAR_START,
                    max=mb.MAPBIOMAS_YEAR_END,
                    step=1,
                    default_value=[mb.MAPBIOMAS_YEAR_END],
                    on_change=AppState.set_mapbiomas_year,
                    width="100%",
                ),
                rx.hstack(
                    rx.text(str(mb.MAPBIOMAS_YEAR_START), size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(str(mb.MAPBIOMAS_YEAR_END), size="1", color_scheme="gray"),
                    width="100%",
                ),
                rx.hstack(
                    rx.text(
                        rx.cond(
                            AppState.compare_enabled,
                            "Opacidade — ano à direita",
                            "Opacidade",
                        ),
                        size="1", color_scheme="gray",
                    ),
                    rx.spacer(),
                    rx.text(AppState.opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5,
                    default_value=[75],
                    on_change=AppState.set_mapbiomas_opacity,
                    width="100%",
                ),
                spacing="2",
                width="100%",
                padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def compare_control() -> rx.Component:
    """Two MapBiomas years at once, split by a draggable vertical divider."""
    return _section(
        "Comparar dois anos",
        rx.hstack(
            rx.switch(checked=AppState.compare_enabled,
                      on_change=AppState.toggle_compare),
            rx.text("Cortina deslizante", size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.compare_enabled,
            rx.vstack(
                rx.hstack(
                    rx.text("Ano à esquerda", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.compare_year.to_string(),
                             color_scheme="amber", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=mb.MAPBIOMAS_YEAR_START, max=mb.MAPBIOMAS_YEAR_END, step=1,
                    default_value=[cm.FOREST_CODE_BASELINE_YEAR],
                    on_change=AppState.set_compare_year, width="100%",
                ),
                rx.hstack(
                    rx.text("Opacidade — ano à esquerda", size="1",
                            color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.compare_opacity_pct.to_string() + "%",
                            size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5,
                    default_value=[75],
                    on_change=AppState.set_compare_opacity,
                    width="100%",
                ),
                rx.text(
                    "Arraste a linha branca no mapa. À direita fica o ano "
                    "selecionado acima em «Cobertura do solo».",
                    size="1", color_scheme="gray",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def change_mask_control() -> rx.Component:
    """Natural vegetation lost or regrown since the Forest Code baseline."""
    return _section(
        "Mudança na vegetação natural",
        rx.hstack(
            rx.switch(checked=AppState.show_change_mask,
                      on_change=AppState.toggle_change_mask),
            rx.text("Candidatos a recuperação", size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_change_mask,
            rx.vstack(
                rx.hstack(
                    rx.text("Ano base", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.change_from_year.to_string(),
                             color_scheme="red", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=mb.MAPBIOMAS_YEAR_START, max=mb.MAPBIOMAS_YEAR_END - 1, step=1,
                    default_value=[cm.FOREST_CODE_BASELINE_YEAR],
                    on_change=AppState.set_change_from_year, width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=cm.CHANGE_COLORS[cm.CHANGE_LOSS]),
                    rx.text("Perda de vegetação natural", size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=cm.CHANGE_COLORS[cm.CHANGE_GAIN]),
                    rx.text("Regeneração", size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.callout(
                    "2008 é o marco do Código Florestal: vegetação nativa suprimida "
                    "depois dessa data tem obrigação de recomposição. Esta camada é "
                    "uma triagem, não um laudo — não considera CAR, APP/RL, porte do "
                    "imóvel nem autorizações.",
                    icon="info", size="1", color_scheme="gray", width="100%",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def status_line() -> rx.Component:
    return rx.hstack(
        rx.cond(
            AppState.ee_error != "",
            rx.icon("triangle-alert", size=14, color="var(--red-9)"),
            rx.cond(
                AppState.ee_ready,
                rx.icon("circle-check", size=14, color="var(--green-9)"),
                rx.spinner(size="1"),
            ),
        ),
        rx.text(AppState.ee_status_label, size="1", color_scheme="gray"),
        spacing="2",
        align="center",
        width="100%",
    )


def point_control() -> rx.Component:
    """The clicked location. Phase 1 hangs the buffer analysis off this panel."""
    return _section(
        "Ponto de estudo",
        rx.cond(
            AppState.has_point,
            rx.vstack(
                rx.hstack(
                    rx.icon("map-pin", size=14, color="var(--jade-11)"),
                    rx.text(AppState.point_label, size="2", weight="medium"),
                    spacing="2", align="center",
                ),
                rx.text("Clique no mapa para escolher outro ponto.",
                        size="1", color_scheme="gray"),
                spacing="1", align_items="start", width="100%",
            ),
            rx.cond(
                AppState.point_error != "",
                rx.callout(AppState.point_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.text("Clique no mapa para escolher um ponto.",
                        size="1", color_scheme="gray"),
            ),
        ),
    )


def layer_panel() -> rx.Component:
    return rx.vstack(
        point_control(),
        rx.divider(),
        basemap_control(),
        rx.divider(),
        mapbiomas_control(),
        rx.divider(),
        compare_control(),
        rx.divider(),
        change_mask_control(),
        rx.spacer(),
        rx.divider(),
        status_line(),
        rx.cond(
            AppState.ee_error != "",
            rx.callout(
                AppState.ee_error,
                icon="triangle-alert",
                color_scheme="red",
                size="1",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing="4",
        align_items="stretch",
        height="100%",
        width="100%",
        padding="1rem",
    )
