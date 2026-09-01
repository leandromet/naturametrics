"""The location search box (ported from camposcope's, trimmed).

One field resolves a coordinate, a município, or a place name — no CAR-code
resolver here, since this app has no property registry. Two result lists
below it, both purely for framing the map (never selecting a point): a
município is exact and local, a place is geocoded and approximate.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState
from .layer_panel import _section

#: One colour per resolver, so the echo line is scannable without being read.
_ECHO_COLOR = {
    "coordenada": "blue",
    "municipio": "amber",
    "lugar": "gray",
    "erro": "red",
}


def _echo_line() -> rx.Component:
    """"lido como: coordenada -12.4979, -55.4977"."""
    return rx.cond(
        AppState.echo,
        rx.hstack(
            rx.text(AppState.tr["search_read_as"], size="1", color_scheme="gray",
                    flex_shrink="0"),
            rx.badge(
                AppState.echo,
                size="1",
                color_scheme=rx.match(
                    AppState.echo_kind,
                    *[(k, v) for k, v in _ECHO_COLOR.items()],
                    "gray",
                ),
                variant="soft",
            ),
            spacing="2",
            align="center",
            width="100%",
            wrap="wrap",
        ),
        rx.fragment(),
    )


def _search_field() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.input(
                rx.input.slot(rx.icon("search", size=14)),
                placeholder=AppState.tr["search_placeholder"],
                value=AppState.query,
                on_change=AppState.set_query,
                on_key_down=lambda key: rx.cond(
                    key == "Enter", AppState.submit_search, rx.noop()
                ),
                size="2",
                width="100%",
            ),
            rx.cond(
                AppState.query,
                rx.icon_button(
                    rx.icon("x", size=14),
                    on_click=AppState.clear_search,
                    size="2",
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.fragment(),
            ),
            spacing="1",
            width="100%",
        ),
        _echo_line(),
        rx.button(
            rx.cond(
                AppState.searching_place,
                AppState.tr["search_button_busy"],
                AppState.tr["search_button"],
            ),
            on_click=AppState.submit_search,
            disabled=AppState.searching_place,
            size="2",
            width="100%",
        ),
        spacing="2",
        width="100%",
    )


def _result_row(*children, on_click) -> rx.Component:
    return rx.box(
        rx.vstack(*children, spacing="1", align_items="start", width="100%"),
        on_click=on_click,
        padding="2",
        border="1px solid var(--gray-5)",
        border_radius="var(--radius-2)",
        cursor="pointer",
        width="100%",
        _hover={"background": "var(--gray-3)"},
    )


def _municipio_hits() -> rx.Component:
    return rx.cond(
        AppState.municipio_hits,
        rx.vstack(
            rx.text(AppState.tr["search_municipios_heading"], size="1",
                    weight="medium", color_scheme="gray"),
            rx.foreach(
                AppState.municipio_hits,
                lambda m: _result_row(
                    rx.text(f"{m['nome']} / {m['uf']}", size="1", weight="medium"),
                    on_click=AppState.choose_municipio(m["cod_municipio_ibge"]),
                ),
            ),
            spacing="1",
            width="100%",
        ),
        rx.fragment(),
    )


def _place_hits() -> rx.Component:
    """Geocoded places. Framing only — no point is selected from here."""
    return rx.cond(
        AppState.place_hits,
        rx.vstack(
            rx.text(AppState.tr["search_places_heading"], size="1",
                    weight="medium", color_scheme="gray"),
            rx.foreach(
                AppState.place_hits,
                lambda p, i: _result_row(
                    rx.text(p["label"], size="1"),
                    on_click=AppState.choose_place(i),
                ),
            ),
            rx.text(AppState.tr["search_places_attribution"], size="1",
                    color_scheme="gray"),
            spacing="1",
            width="100%",
        ),
        rx.fragment(),
    )


def search_panel() -> rx.Component:
    return _section(
        AppState.tr["search_title"],
        _search_field(),
        rx.cond(
            AppState.search_error != "",
            rx.callout(AppState.search_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.fragment(),
        ),
        _municipio_hits(),
        _place_hits(),
        info=AppState.tr["search_info"],
    )
