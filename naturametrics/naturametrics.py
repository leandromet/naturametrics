"""Naturametrics — land-use history and landscape analysis.

App entry point. See doc/ for premises, architecture and roadmap.
"""

from __future__ import annotations

import logging

import reflex as rx

from .components.layout import ACCENT
from .pages.index import index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = rx.App(
    theme=rx.theme(appearance="light", accent_color=ACCENT, radius="medium"),
    style={"fontFamily": "Inter, system-ui, sans-serif"},
    head_components=[
        # Without this, mobile browsers lay the page out at ~980px and then zoom
        # out to fit — every responsive breakpoint would evaluate as "desktop"
        # and the whole mobile layout would never appear.
        rx.el.meta(
            name="viewport",
            content="width=device-width, initial-scale=1, viewport-fit=cover",
        ),
        rx.el.meta(name="theme-color", content="#ffffff"),
    ],
)

app.add_page(
    index,
    route="/",
    title="Naturametrics — História de uso da terra",
    description=(
        "Análise da história de uso da terra e da paisagem no Brasil a partir de "
        "MapBiomas, Hansen e Earth Engine."
    ),
)
