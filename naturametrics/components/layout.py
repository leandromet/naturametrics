"""Application shell: header + sidebar + map-dominant workspace.

Responsive across three shapes, using Reflex's breakpoint lists
(``[initial, 30em, 48em, 62em]`` → phone, large phone, tablet, desktop):

* **Desktop (≥62em)** — fixed 320 px sidebar beside a full-height map, results
  drawer pinned under the map. Nothing scrolls except the panels themselves.
* **Tablet / phone** — the sidebar becomes an overlay drawer opened from the
  header, the map takes the full width at a fixed viewport fraction, and the
  results flow underneath in a single scrolling column.

The map is deliberately given a *fixed* height on small screens rather than
``flex: 1``: a flex-sized map inside a scrolling column collapses to nothing,
and Leaflet renders a single grey tile when its container has no height.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState
from .help import header_actions

ACCENT = "jade"  # distinct from Yvynation's palette — see doc/07-ui-ux.md §8

HEADER_H = "56px"

#: Shown only below the desktop breakpoint.
_MOBILE_ONLY = ["flex", "flex", "flex", "none"]
#: Shown only at the desktop breakpoint and above.
_DESKTOP_ONLY = ["none", "none", "none", "flex"]


def header() -> rx.Component:
    return rx.hstack(
        rx.button(
            rx.icon("panel-left", size=18),
            on_click=AppState.toggle_sidebar,
            size="1",
            variant="ghost",
            color_scheme="gray",
            display=_MOBILE_ONLY,
            aria_label="Abrir painel de camadas",
        ),
        rx.hstack(
            rx.icon("layers", size=20, color=f"var(--{ACCENT}-11)"),
            rx.heading("Naturametrics", size=rx.breakpoints(initial="3", md="4"),
                       weight="bold", white_space="nowrap"),
            rx.badge("v0.1", variant="soft", color_scheme="gray", size="1",
                     display=["none", "flex", "flex", "flex"]),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.text(
            "História de uso da terra e análise da paisagem",
            size="2",
            color_scheme="gray",
            display=["none", "none", "none", "block"],
        ),
        rx.box(width="1rem", display=["none", "none", "none", "block"]),
        header_actions(),
        width="100%",
        min_width="0",
        padding=["0.5rem 0.6rem", "0.5rem 0.75rem", "0.75rem 1rem", "0.75rem 1rem"],
        border_bottom="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        align="center",
        spacing="2",
        height=HEADER_H,
        flex_shrink="0",
    )


def _mobile_sidebar(sidebar: rx.Component) -> rx.Component:
    """Overlay drawer for phone and tablet widths."""
    return rx.fragment(
        rx.cond(
            AppState.sidebar_open,
            rx.box(
                on_click=AppState.toggle_sidebar,
                position="fixed",
                top=HEADER_H,
                left="0",
                width="100vw",
                height=f"calc(100dvh - {HEADER_H})",
                background="rgba(0,0,0,0.45)",
                z_index="900",
                display=_MOBILE_ONLY,
            ),
            rx.fragment(),
        ),
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text("Camadas e análise", size="2", weight="bold"),
                    rx.spacer(),
                    rx.button(
                        rx.icon("x", size=16),
                        on_click=AppState.toggle_sidebar,
                        size="1", variant="ghost", color_scheme="gray",
                        aria_label="Fechar painel",
                    ),
                    width="100%", align="center",
                    padding="0.6rem 0.75rem 0",
                ),
                sidebar,
                spacing="0", align_items="stretch", width="100%",
            ),
            position="fixed",
            top=HEADER_H,
            left="0",
            width=["86vw", "78vw", "360px", "360px"],
            max_width="380px",
            height=f"calc(100dvh - {HEADER_H})",
            background="var(--color-panel-solid)",
            border_right="1px solid var(--gray-5)",
            box_shadow="4px 0 24px rgba(0,0,0,.18)",
            overflow_y="auto",
            z_index="901",
            # Slide rather than pop: transform keeps it off the paint path when
            # closed, and avoids the layout shift a display toggle would cause.
            transform=rx.cond(AppState.sidebar_open, "translateX(0)", "translateX(-105%)"),
            transition="transform .22s ease",
            display=_MOBILE_ONLY,
        ),
    )


def workspace(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.fragment(
        _mobile_sidebar(sidebar),
        rx.hstack(
            # Static sidebar, desktop only.
            rx.box(
                sidebar,
                width="320px",
                min_width="320px",
                height="100%",
                border_right="1px solid var(--gray-5)",
                background="var(--color-panel-solid)",
                overflow_y="auto",
                display=_DESKTOP_ONLY,
            ),
            rx.box(
                main,
                flex="1",
                height=["auto", "auto", "auto", "100%"],
                min_width="0",
                position="relative",
            ),
            width="100%",
            flex="1",
            spacing="0",
            align_items="stretch",
            # Below desktop the whole column scrolls; at desktop nothing does.
            overflow_y=["auto", "auto", "auto", "hidden"],
            overflow_x="hidden",
        ),
    )


def shell(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.vstack(
        header(),
        workspace(sidebar, main),
        width="100vw",
        # dvh, not vh: on mobile browsers vh includes the collapsing URL bar, so
        # 100vh leaves the bottom of the page permanently under the chrome.
        height=["100dvh", "100dvh", "100dvh", "100vh"],
        spacing="0",
        align_items="stretch",
        overflow="hidden",
        on_mount=AppState.initialise,
    )
