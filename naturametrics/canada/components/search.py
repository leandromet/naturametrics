"""The Canada page's location search box (the Brazil page's, trimmed).

One field resolves a postal code, a coordinate, or a place name / street
address, and **says how it read the input** before acting — the line that
stops a transposed coordinate pair from quietly resolving somewhere wrong.
A place frames the map and drops a pin; only a coordinate picks a study point.
"""

from __future__ import annotations

import reflex as rx

from ..state import CanadaState as S
from .layer_panel import _section

#: One colour per resolver, so the echo line is scannable without being read.
_ECHO_COLOR = {"postal": "cyan", "coordenada": "blue", "lugar": "gray",
               "erro": "red"}

#: Precision → badge colour, same vocabulary as the Brazil page.
_PRECISION_COLOR = {
    "endereco": "grass", "rua": "grass", "cep": "cyan", "bairro": "amber",
    "cidade": "amber", "regiao": "gray", "lugar": "gray",
}


def _echo_line() -> rx.Component:
    return rx.cond(
        S.echo,
        rx.hstack(
            rx.text(S.tr["search_read_as"], size="1", color_scheme="gray",
                    flex_shrink="0"),
            rx.badge(
                S.echo, size="1", variant="soft",
                color_scheme=rx.match(
                    S.echo_kind, *[(k, v) for k, v in _ECHO_COLOR.items()],
                    "gray"),
                style={"whiteSpace": "normal", "height": "auto", "maxWidth": "100%"},
            ),
            spacing="2", align="center", width="100%", wrap="wrap",
        ),
        rx.fragment(),
    )


def _precision_badge(precision) -> rx.Component:
    return rx.badge(
        rx.match(precision,
                 *[(k, S.tr[f"precision_{k}"]) for k in _PRECISION_COLOR],
                 S.tr["precision_lugar"]),
        size="1", variant="soft", flex_shrink="0",
        color_scheme=rx.match(precision,
                              *[(k, v) for k, v in _PRECISION_COLOR.items()],
                              "gray"),
    )


def _place_hits() -> rx.Component:
    return rx.cond(
        S.place_hits,
        rx.vstack(
            rx.text(S.tr["search_places_heading"], size="1", weight="medium",
                    color_scheme="gray"),
            rx.foreach(
                S.place_hits,
                lambda p, i: rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.text(p["title"], size="1", weight="medium"),
                            rx.spacer(),
                            _precision_badge(p["precision"]),
                            spacing="2", align="start", width="100%",
                        ),
                        rx.cond(p["subtitle"],
                                rx.text(p["subtitle"], size="1",
                                        color_scheme="gray"),
                                rx.fragment()),
                        spacing="1", align_items="start", width="100%",
                    ),
                    on_click=S.choose_place(i),
                    padding="2", border="1px solid var(--gray-5)",
                    border_radius="var(--radius-2)", cursor="pointer",
                    width="100%", _hover={"background": "var(--gray-3)"},
                ),
            ),
            rx.text(S.tr["search_places_note"], size="1", color_scheme="gray"),
            rx.text(S.place_attribution, size="1", color_scheme="gray"),
            spacing="1", width="100%",
        ),
        rx.fragment(),
    )


def search_panel() -> rx.Component:
    return _section(
        S.tr["search_title"],
        rx.hstack(
            rx.input(
                rx.input.slot(rx.icon("search", size=14)),
                placeholder=S.tr["search_placeholder"],
                value=S.query, on_change=S.set_query,
                on_key_down=lambda key: rx.cond(
                    key == "Enter", S.submit_search, rx.noop()),
                size="2", width="100%",
            ),
            rx.cond(
                S.query,
                rx.icon_button(rx.icon("x", size=14), on_click=S.clear_search,
                               size="2", variant="soft", color_scheme="gray",
                               aria_label=S.tr["search_clear_aria"]),
                rx.fragment(),
            ),
            spacing="1", width="100%",
        ),
        _echo_line(),
        rx.button(
            rx.cond(S.searching_place, S.tr["search_button_busy"],
                    S.tr["search_button"]),
            on_click=S.submit_search, disabled=S.searching_place,
            size="2", width="100%",
        ),
        rx.cond(
            S.search_error,
            rx.callout(S.search_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.fragment(),
        ),
        _place_hits(),
    )
