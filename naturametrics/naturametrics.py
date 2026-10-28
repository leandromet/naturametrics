"""Naturametrics — land-use history and landscape analysis.

App entry point. See doc/ for premises, architecture and roadmap.
"""

from __future__ import annotations

import logging

import reflex as rx

from .api import register as register_api
from .canada.pages.index import canada_index
from .canada.state import CanadaState
from .components.layout import ACCENT
from .config.settings import GA_MEASUREMENT_ID
from .pages.demonstracao import demonstracao
from .pages.index import index
from .state import AppState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _ga_head_components() -> list[rx.Component]:
    """GA4 tag, only when NM_GA_MEASUREMENT_ID is set (empty in local dev)."""
    if not GA_MEASUREMENT_ID:
        return []
    return [
        rx.el.script(src=f"https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}", async_=True),
        rx.el.script(f"""
            window.dataLayer = window.dataLayer || [];
            function gtag(){{ dataLayer.push(arguments); }}
            gtag('js', new Date());
            gtag('config', '{GA_MEASUREMENT_ID}');
        """),
    ]


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
        *_ga_head_components(),
        # Idle tabs otherwise keep the Reflex WebSocket reconnecting forever,
        # which pins a billed Cloud Run instance with nobody using it — see
        # assets/idle_guard.js and assets/paused.html.
        # Reflex serves the app-root assets/ folder at the site root, so the
        # file is /idle_guard.js — the old /assets/idle_guard.js fell through
        # to the SPA's HTML ("Unexpected token '<'") and the guard never ran.
        rx.el.script(src="/idle_guard.js", defer=True),
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
    on_load=AppState.adopt_url_params,
)

# The scrolling walkthrough of one real point (doc in pages/demonstracao.py).
# Its numbers come over HTTP from /_demonstracao/naturametrics.json, so the
# page has no state of its own and no on_load.
app.add_page(
    demonstracao,
    route="/demonstracao",
    title="Naturametrics — demonstração passo a passo",
    description=(
        "Como ler a paisagem em volta de um ponto, raio por raio: MapBiomas, "
        "pixel do ponto, mudança desde 2008, idade da vegetação, métricas de "
        "paisagem, biomassa, IBGE e IBAMA, com um conglomerado real do IFN."
    ),
)

# The Canada page is a self-contained sibling under naturametrics/canada/ — its
# own state root, services, components and translations. It shares the Earth
# Engine client, the buffer geometry, the tile cache, the ODS writer and the
# Leaflet component, and nothing else: the two countries' datasets have
# different years, extents and legends, so a shared state root would mean every
# var carrying a "which country" qualifier.
app.add_page(
    canada_index,
    route="/canada",
    title="Naturametrics Canada — Crop inventory and forest change",
    description=(
        "Land-use history, forest stand age and forest change anywhere in "
        "Canada, from the AAFC Annual Crop Inventory, NTEMS and Hansen Global "
        "Forest Change on Earth Engine."
    ),
    on_load=CanadaState.adopt_lang_param,
)

# The biome polygons are fetched by the browser over HTTP, not pushed through
# the WebSocket — see naturametrics/api/__init__.py for why.
register_api(app)
