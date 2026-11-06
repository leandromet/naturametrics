"""Application shell for the USA page.

Structurally identical to the Brazil shell (same breakpoints, same mobile drawer,
same dvh reasoning) but bound to ``USState`` and carrying the links to
the Brazil and Canada pages. The geometry is not re-derived here — if the responsive rules
ever change, they change in both, and the comments in
``naturametrics/components/layout.py`` are the explanation for both.
"""

from __future__ import annotations

import reflex as rx

from ...components.suite_links import suite_links
from ..state import USState as S
from .help import header_actions

ACCENT = "jade"
HEADER_H = "56px"

_MOBILE_ONLY = ["flex", "flex", "flex", "none"]
_DESKTOP_ONLY = ["none", "none", "none", "flex"]


def language_switcher() -> rx.Component:
    return rx.segmented_control.root(
        rx.segmented_control.item("🇧🇷 PT", value="pt"),
        rx.segmented_control.item("🇺🇸 EN", value="en"),
        value=S.language,
        on_change=S.set_language,
        size="1",
        aria_label=S.tr["language_label"],
    )


def brazil_link() -> rx.Component:
    """Back to the Brazil page, carrying the chosen language."""
    return rx.link(
        rx.button(
            rx.text(S.tr["go_to_brazil"],
                    display=["none", "none", "block", "block"]),
            size="1", variant="soft", color_scheme="gray",
            aria_label=S.tr["go_to_brazil"],
        ),
        href=S.brazil_href,
    )


def canada_link() -> rx.Component:
    """To the Canada page, carrying the chosen language."""
    return rx.link(
        rx.button(
            rx.text(S.tr["go_to_canada"],
                    display=["none", "none", "block", "block"]),
            size="1", variant="soft", color_scheme="gray",
            aria_label=S.tr["go_to_canada"],
        ),
        href=S.canada_href,
    )


def header() -> rx.Component:
    return rx.hstack(
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
        suite_links("naturametrics", region="usa", language=S.language,
                    accent=ACCENT),
        brazil_link(),
        canada_link(),
        language_switcher(),
        header_actions(),
        width="100%", min_width="0",
        padding=["0.5rem 0.6rem", "0.5rem 0.75rem", "0.75rem 1rem", "0.75rem 1rem"],
        border_bottom="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        align="center", spacing="2", height=HEADER_H, flex_shrink="0",
    )


def workspace(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.fragment(
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
