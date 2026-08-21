"""Application shell for the Canada page.

Structurally identical to the Brazil shell (same breakpoints, same mobile drawer,
same dvh reasoning) but bound to ``CanadaState`` and carrying the link back to
the Brazil page. The geometry is not re-derived here — if the responsive rules
ever change, they change in both, and the comments in
``naturametrics/components/layout.py`` are the explanation for both.
"""

from __future__ import annotations

import reflex as rx

from ..state import CanadaState as S
from .help import header_actions

ACCENT = "jade"
HEADER_H = "56px"

_MOBILE_ONLY = ["flex", "flex", "flex", "none"]
_DESKTOP_ONLY = ["none", "none", "none", "flex"]


def language_switcher() -> rx.Component:
    return rx.segmented_control.root(
        rx.segmented_control.item("🇧🇷 PT", value="pt"),
        rx.segmented_control.item("🇨🇦 EN", value="en"),
        value=S.language,
        on_change=S.set_language,
        size="1",
        aria_label=S.tr["language_label"],
    )


def brazil_link() -> rx.Component:
    """Back to the Brazil page, carrying the chosen language."""
    return rx.link(
        rx.button(
            rx.text("🇧🇷", font_size="0.95rem"),
            rx.text(S.tr["go_to_brazil"],
                    display=["none", "none", "block", "block"]),
            size="1", variant="soft", color_scheme="gray",
            aria_label=S.tr["go_to_brazil"],
        ),
        href=S.brazil_href,
    )


def header() -> rx.Component:
    return rx.hstack(
        rx.button(
            rx.icon("panel-left", size=18),
            on_click=S.toggle_sidebar,
            size="1", variant="ghost", color_scheme="gray",
            display=_MOBILE_ONLY,
            aria_label=S.tr["nav_toggle_layers_aria"],
        ),
        rx.hstack(
            rx.icon("layers", size=20, color=f"var(--{ACCENT}-11)"),
            rx.heading("Naturametrics", size=rx.breakpoints(initial="3", md="4"),
                       weight="bold", white_space="nowrap"),
            rx.badge(S.tr["nav_title_suffix"], variant="soft",
                     color_scheme="jade", size="1"),
            spacing="2", align="center",
        ),
        rx.spacer(),
        rx.text(S.tr["nav_subtitle"], size="2", color_scheme="gray",
                display=["none", "none", "none", "block"]),
        rx.box(width="1rem", display=["none", "none", "none", "block"]),
        brazil_link(),
        language_switcher(),
        header_actions(),
        width="100%", min_width="0",
        padding=["0.5rem 0.6rem", "0.5rem 0.75rem", "0.75rem 1rem", "0.75rem 1rem"],
        border_bottom="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        align="center", spacing="2", height=HEADER_H, flex_shrink="0",
    )


def _mobile_sidebar(sidebar: rx.Component) -> rx.Component:
    return rx.fragment(
        rx.cond(
            S.sidebar_open,
            rx.box(
                on_click=S.toggle_sidebar,
                position="fixed", top=HEADER_H, left="0",
                width="100vw", height=f"calc(100dvh - {HEADER_H})",
                background="rgba(0,0,0,0.45)", z_index="900",
                display=_MOBILE_ONLY,
            ),
            rx.fragment(),
        ),
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text(S.tr["drawer_title"], size="2", weight="bold"),
                    rx.spacer(),
                    rx.button(
                        rx.icon("x", size=16), on_click=S.toggle_sidebar,
                        size="1", variant="ghost", color_scheme="gray",
                        aria_label=S.tr["drawer_close_aria"],
                    ),
                    width="100%", align="center", padding="0.6rem 0.75rem 0",
                ),
                sidebar,
                spacing="0", align_items="stretch", width="100%",
            ),
            position="fixed", top=HEADER_H, left="0",
            width=["86vw", "78vw", "360px", "360px"], max_width="380px",
            height=f"calc(100dvh - {HEADER_H})",
            background="var(--color-panel-solid)",
            border_right="1px solid var(--gray-5)",
            box_shadow="4px 0 24px rgba(0,0,0,.18)",
            overflow_y="auto", z_index="901",
            transform=rx.cond(S.sidebar_open, "translateX(0)", "translateX(-105%)"),
            transition="transform .22s ease",
            display=_MOBILE_ONLY,
        ),
    )


def workspace(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.fragment(
        _mobile_sidebar(sidebar),
        rx.hstack(
            rx.box(
                sidebar,
                width="320px", min_width="320px", height="100%",
                border_right="1px solid var(--gray-5)",
                background="var(--color-panel-solid)",
                overflow_y="auto", display=_DESKTOP_ONLY,
            ),
            rx.box(main, flex="1",
                   height=["auto", "auto", "auto", "100%"],
                   min_width="0", position="relative"),
            width="100%", flex="1", spacing="0", align_items="stretch",
            overflow_y=["auto", "auto", "auto", "hidden"], overflow_x="hidden",
        ),
    )


def shell(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.vstack(
        header(),
        workspace(sidebar, main),
        width="100vw",
        height=["100dvh", "100dvh", "100dvh", "100vh"],
        spacing="0", align_items="stretch", overflow="hidden",
        on_mount=S.initialise,
    )
