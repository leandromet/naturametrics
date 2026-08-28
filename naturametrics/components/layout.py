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

#: Shown only at the desktop breakpoint and above.
_DESKTOP_ONLY = ["none", "none", "none", "flex"]


def language_switcher() -> rx.Component:
    return rx.segmented_control.root(
        rx.segmented_control.item("🇧🇷 PT", value="pt"),
        rx.segmented_control.item("🇨🇦 EN", value="en"),
        value=AppState.language,
        on_change=AppState.set_language,
        size="1",
        aria_label=AppState.tr["language_label"],
    )


def canada_link() -> rx.Component:
    """Across to the Canada page, carrying the chosen language.

    A plain link rather than an event: ``/canada`` is a separate Reflex page with
    its own state root, so this is a navigation, not a mode switch inside this
    one.
    """
    return rx.link(
        rx.button(
            rx.text("🇨🇦", font_size="0.95rem"),
            rx.text(AppState.tr["go_to_canada"],
                    display=["none", "none", "block", "block"]),
            size="1", variant="soft", color_scheme="gray",
            aria_label=AppState.tr["go_to_canada"],
        ),
        href=AppState.canada_href,
    )


def header() -> rx.Component:
    # Below desktop, the sidebar is folded into the mobile bottom sheet
    # (pages/index.py::_mobile_sheet()) — always mounted, opened by dragging
    # its own handle, not by a boolean open/close toggle the way the old
    # overlay drawer worked. A header button pointing at it turned out to be
    # the wrong fix for "nobody notices how to open this": a small grey
    # ghost-icon button competing with five other header controls was easy
    # to miss too. The sheet's handle is now a solid, accent-coloured tab
    # (pages/index.py::_drag_handle()) — visible at every scroll position,
    # not one more thing to find in the header — so the button was removed
    # rather than also made louder; two competing "open" affordances would
    # be its own kind of confusing.
    return rx.hstack(
        rx.hstack(
            rx.icon("layers", size=20, color=f"var(--{ACCENT}-11)"),
            rx.heading("Naturametrics", size=rx.breakpoints(initial="3", md="4"),
                       weight="bold", white_space="nowrap"),
            rx.badge("v0.3.1", variant="soft", color_scheme="gray", size="1",
                     display=["none", "flex", "flex", "flex"]),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.text(
            AppState.tr["nav_subtitle"],
            size="2",
            color_scheme="gray",
            display=["none", "none", "none", "block"],
        ),
        rx.box(width="1rem", display=["none", "none", "none", "block"]),
        canada_link(),
        language_switcher(),
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


#: Below desktop, the sidebar no longer has an overlay-drawer form of its
#: own — its content (``layer_panel()``) is folded into the mobile bottom
#: sheet built in ``pages/index.py::_mobile_sheet()``, alongside
#: ``results_drawer()``. ``workspace()`` below only ever mounts one Leaflet
#: map (the sheet is a viewport-``position: fixed`` overlay, not a second
#: map instance) — see ``pages/index.py::workspace_main()`` for how the map
#: and the results content it used to sit above/below now share one flex
#: column across every breakpoint.
def workspace(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.hstack(
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
            height="100%",
            min_width="0",
            position="relative",
        ),
        width="100%",
        flex="1",
        spacing="0",
        align_items="stretch",
        # Nothing scrolls at the page level at any breakpoint any more: the
        # mobile sheet owns its own internal scroll, and desktop never
        # needed the column to scroll in the first place.
        overflow="hidden",
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
