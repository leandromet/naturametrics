"""The hover card for an IFN conglomerado.

Floats over the map rather than living in the sidebar: it describes something the
cursor is pointing at, and a panel 300 px away that updates as you move would make
the reader look back and forth to pair a name with a place.

It is deliberately a *preview*. Six classes, the current composition against
1985, and a line telling the user that clicking runs the real analysis — see
``state/_conglomerado.py`` for why hovering cannot afford more.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState


def _class_row(row: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.box(width="9px", height="9px", border_radius="2px",
               background=row["color"], flex_shrink="0"),
        rx.text(row["name"], size="1", style={
            "whiteSpace": "nowrap", "overflow": "hidden",
            "textOverflow": "ellipsis"}),
        rx.spacer(),
        rx.text(row["pct"], size="1", weight="medium"),
        rx.text(row["delta"], size="1", color_scheme="gray",
                style={"minWidth": "58px", "textAlign": "right"}),
        spacing="2", align="center", width="100%",
    )


def conglomerado_card() -> rx.Component:
    return rx.cond(
        AppState.hover_visible,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon("map-pin", size=13, color="var(--jade-11)"),
                    rx.text(AppState.hover_conglomerado, size="2", weight="bold"),
                    rx.spacer(),
                    rx.cond(AppState.hover_loading, rx.spinner(size="1"),
                            rx.fragment()),
                    width="100%", align="center", spacing="2",
                ),
                rx.text(AppState.hover_place, size="1", color_scheme="gray"),
                rx.cond(
                    AppState.hover_bioma != "",
                    rx.badge(AppState.hover_bioma, size="1", variant="soft",
                             color_scheme="green"),
                    rx.fragment(),
                ),
                rx.cond(
                    AppState.hover_error != "",
                    rx.text(AppState.hover_error, size="1", color="var(--red-11)"),
                    rx.fragment(),
                ),
                rx.cond(
                    AppState.hover_rows.length() > 0,
                    rx.vstack(
                        rx.divider(),
                        rx.foreach(AppState.hover_rows, _class_row),
                        rx.text(AppState.hover_natural, size="1",
                                weight="medium", color="var(--jade-11)"),
                        spacing="1", width="100%",
                    ),
                    rx.fragment(),
                ),
                rx.text(AppState.hover_note, size="1", color_scheme="gray",
                        style={"lineHeight": "1.35"}),
                spacing="1", align_items="start", width="100%",
            ),
            position="absolute",
            # Top-LEFT, not top-right: `map_legend.py`'s box lives at
            # top-right (12px/12px, z-index 900) and this card used to sit
            # at nearly the same spot (0.6rem/0.6rem, z-index 800) — the two
            # are shown independently (one on "a layer is active", the other
            # on "hovering an IFN point"), so nothing stopped both being on
            # at once, and the legend always won, fully covering the card.
            # On mobile it was worse: this card's width goes `auto` (up to
            # ~full screen minus padding), so it didn't just clip the
            # legend's corner, it could bury the whole thing. Top offset
            # clears Leaflet's own zoom control, which docks top-left.
            top="4.75rem",
            left="0.6rem",
            width=["auto", "auto", "290px", "290px"],
            max_width="calc(100% - 1.2rem)",
            padding="0.6rem 0.7rem",
            background="var(--color-panel-solid)",
            border="1px solid var(--gray-5)",
            border_radius="8px",
            box_shadow="0 4px 18px rgba(0,0,0,.18)",
            # Above Leaflet's own panes and controls, but never intercepting the
            # pointer: a card that swallowed clicks would block the map exactly
            # where the user is working.
            z_index="800",
            pointer_events="none",
        ),
        rx.fragment(),
    )
