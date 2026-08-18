"""Application shell: header + sidebar + map-dominant workspace."""

from __future__ import annotations

import reflex as rx

from ..state import AppState

ACCENT = "jade"  # distinct from Yvynation's palette — see doc/07-ui-ux.md §8


def header() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.icon("layers", size=20, color=f"var(--{ACCENT}-11)"),
            rx.heading("Naturametrics", size="4", weight="bold"),
            rx.badge("v0.1 · fase 0", variant="soft", color_scheme="gray", size="1"),
            spacing="3",
            align="center",
        ),
        rx.spacer(),
        rx.text(
            "História de uso da terra e análise da paisagem",
            size="2",
            color_scheme="gray",
            display=["none", "none", "block"],
        ),
        width="100%",
        padding="0.75rem 1rem",
        border_bottom="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        align="center",
        height="56px",
        flex_shrink="0",
    )


def workspace(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.hstack(
        rx.box(
            sidebar,
            width="320px",
            min_width="320px",
            height="100%",
            border_right="1px solid var(--gray-5)",
            background="var(--color-panel-solid)",
            overflow_y="auto",
        ),
        rx.box(main, flex="1", height="100%", position="relative"),
        width="100%",
        flex="1",
        spacing="0",
        align_items="stretch",
        overflow="hidden",
    )


def shell(sidebar: rx.Component, main: rx.Component) -> rx.Component:
    return rx.vstack(
        header(),
        workspace(sidebar, main),
        width="100vw",
        height="100vh",
        spacing="0",
        align_items="stretch",
        overflow="hidden",
        on_mount=AppState.initialise,
    )
