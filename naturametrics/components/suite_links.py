"""Links between the UmaTerra platforms, each explained on hover.

Camposcope (one rural property), Naturametrics (any clicked point), Yvynation
(protected territories) and muda-clima (the climate exposure of the land around a
point) answer different questions about the same land, and a reader who starts
in one often wants another. This is the one
control in every header that jumps between them.

* **Wide screens** (≥ 1880 px): compact chips — icon and name — with a
  hover/focus tooltip saying what each is for: the UmaTerra portal (home of all
  the platforms) first, then the four platforms. (Was 1280 px with three; a
  fifth chip no longer fits the headers below ~1855 px.) The current platform is
  highlighted and is not a link.
* **Everywhere else** (a phone has no hover, and no room): one "platforms"
  button that opens a menu showing the same descriptions in full.
  ``compact=True`` forces this at every width, for a header that is already
  full (Yvynation's workspace navbar).

Each link keeps the **region** (a Brazil page links to the others' Brazil page,
a Canada page to their ``/canada``; muda-clima has one page for both countries, ``/app/``, and ``?region=ca`` frames Canada) and the **language** (``?lang=``, which every
platform honours on load; one that does not know the language keeps its own).

muda-clima is not a Reflex app: its header renders the same entries
from its own ``app/web/suite.py``. Keep the descriptions in step with it.

Shared by the three apps and checked by hash: the canonical copy is
``/server/naturametrics/naturametrics/components/suite_links.py``. Edit it there, then run
``python scripts/sync_shared_files.py`` in Naturametrics, which copies it to
Camposcope and Yvynation and rewrites each app's ``tests/shared_files.sha256``.
An edit made in any other copy fails that app's ``tests/test_shared_files.py``.

It reads nothing from any app's state or
translation tables: the descriptions live here, in en / pt / es / fr, so a
platform that only offers two languages can still describe the others in a
third.

Base URLs default to the production subdomains; set ``UMATERRA_URL_CAMPOSCOPE`` /
``UMATERRA_URL_NATURAMETRICS`` / ``UMATERRA_URL_YVYNATION`` (and
``UMATERRA_URL_PORTAL`` for the portal) to point them at local servers while
developing.
"""

from __future__ import annotations

import os

import reflex as rx

PLATFORMS = ("camposcope", "naturametrics", "yvynation", "clima")

PORTAL = "portal"

_DEFAULT_URLS = {
    "portal": "https://umaterra.com.br",
    "camposcope": "https://camposcope.umaterra.com.br",
    "naturametrics": "https://naturametrics.umaterra.com.br",
    "yvynation": "https://yvynation.umaterra.com.br",
    "clima": "https://clima.umaterra.com.br",
}

NAMES = {"portal": "UmaTerra", "camposcope": "Camposcope",
         "naturametrics": "Naturametrics", "yvynation": "Yvynation",
         "clima": "muda-clima"}

#: The icon each app already carries in its own header.
ICONS = {"portal": "globe", "camposcope": "scan-search", "naturametrics": "layers",
         "yvynation": "trees", "clima": "cloud-sun-rain"}

#: What each platform is for. One or two sentences: it is read in a tooltip.
DESCRIPTIONS = {
    "portal": {
        "en": "The home page for all the platforms: what each one is for, who it "
              "helps, and how to support the project. Free and open source.",
        "pt": "A página inicial de todas as plataformas: para que serve cada uma, a "
              "quem ajuda e como apoiar o projeto. Gratuitas e de código aberto.",
        "es": "La página principal de todas las plataformas: para qué sirve cada una, "
              "a quién ayuda y cómo apoyar el proyecto. Gratuitas y de código abierto.",
        "fr": "La page d'accueil de toutes les plateformes : à quoi sert chacune, qui "
              "elle aide et comment soutenir le projet. Gratuites et à code source "
              "ouvert.",
    },
    "camposcope": {
        "en": "Analyses one rural property at a time — its registered boundary "
              "(the CAR in Brazil, ParcelMap BC parcels in Canada) and the land "
              "around it: cover, forest loss, biomass and fire.",
        "pt": "Analisa um imóvel rural por vez — o limite cadastrado (CAR no Brasil, "
              "parcelas do ParcelMap BC no Canadá) e a terra ao redor: cobertura, "
              "perda florestal, biomassa e fogo.",
        "es": "Analiza un inmueble rural a la vez — su límite registrado (el CAR en "
              "Brasil, parcelas de ParcelMap BC en Canadá) y la tierra alrededor: "
              "cobertura, pérdida forestal, biomasa y fuego.",
        "fr": "Analyse une propriété rurale à la fois — sa limite enregistrée (le CAR "
              "au Brésil, les parcelles de ParcelMap BC au Canada) et les terres "
              "autour : couverture, perte forestière, biomasse et feux.",
    },
    "naturametrics": {
        "en": "Land-use history and landscape metrics around any point you click "
              "(Brazil: MapBiomas since 1985 and forest-inventory plots; Canada: "
              "crop inventory, forest age and forest change).",
        "pt": "Histórico de uso da terra e métricas de paisagem ao redor de qualquer "
              "ponto clicado (Brasil: MapBiomas desde 1985 e conglomerados do "
              "inventário florestal; Canadá: inventário agrícola, idade e mudança "
              "da floresta).",
        "es": "Historial de uso del suelo y métricas del paisaje alrededor de "
              "cualquier punto en que haga clic (Brasil: MapBiomas desde 1985 y "
              "parcelas del inventario forestal; Canadá: inventario agrícola, edad "
              "y cambio forestal).",
        "fr": "Historique d'usage du sol et métriques du paysage autour de n'importe "
              "quel point cliqué (Brésil : MapBiomas depuis 1985 et placettes de "
              "l'inventaire forestier; Canada : inventaire des cultures, âge et "
              "changement de la forêt).",
    },
    "yvynation": {
        "en": "Land-cover change inside Brazil's Indigenous lands and conservation "
              "units, and Canada's protected areas, or inside areas you draw — with "
              "maps, charts and reports.",
        "pt": "Mudança da cobertura do solo dentro das terras indígenas e unidades de "
              "conservação do Brasil e das áreas protegidas do Canadá, ou de áreas "
              "que você desenha — com mapas, gráficos e relatórios.",
        "es": "Cambio de la cobertura del suelo dentro de las tierras indígenas y "
              "unidades de conservación de Brasil y las áreas protegidas de Canadá, "
              "o de áreas que usted dibuje — con mapas, gráficos e informes.",
        "fr": "Changement de l'occupation du sol dans les terres autochtones et les "
              "unités de conservation du Brésil et les aires protégées du Canada, ou "
              "dans des zones que vous dessinez — avec cartes, graphiques et rapports.",
    },
    "clima": {
        "en": "Climate exposure of the land around any point you click, in Brazil and "
              "Canada: today's land use read against CMIP6 projections of heat, "
              "drought and heavy rain — plus measured fire, terrain, rain and wind.",
        "pt": "Exposição climática da terra ao redor de qualquer ponto clicado, no "
              "Brasil e no Canadá: o uso atual lido junto com as projeções CMIP6 de "
              "calor, seca e chuva forte — e fogo, terreno, chuva e vento medidos.",
        "es": "Exposición climática de la tierra alrededor de cualquier punto en que "
              "haga clic, en Brasil y Canadá: el uso actual leído junto a las "
              "proyecciones CMIP6 de calor, sequía y lluvia intensa — además de "
              "fuego, terreno, lluvia y viento medidos.",
        "fr": "Exposition climatique des terres autour de n'importe quel point cliqué, "
              "au Brésil et au Canada : l'usage actuel lu avec les projections CMIP6 "
              "de chaleur, de sécheresse et de pluies intenses — ainsi que feux, "
              "terrain, pluie et vent mesurés.",
    },
}

HERE = {"en": "You are here", "pt": "Você está aqui", "es": "Está aquí",
        "fr": "Vous êtes ici"}
TITLE = {"en": "UmaTerra platforms", "pt": "Plataformas UmaTerra",
         "es": "Plataformas UmaTerra", "fr": "Plateformes UmaTerra"}

_LANGS = ("en", "pt", "es", "fr")

#: Chips need this much width; below it the menu button is used instead.
#: Measured in Naturametrics' header (2026-10-14, five chips, the widest header
#: of the three): the rightmost button ("Aviso sobre uso de IA") ends at 1904 px on
#: a 1920 px screen and stops tracking the screen width below ~1855 px, where it
#: overflows (1839 px at 1800). So chips from 1880 px; 1080p screens get them.
#: A plain CSS media query: Reflex's breakpoint list has nothing between 1536 and
#: infinity.
_CHIPS_WIDTH = "@media (min-width: 1880px)"
_CHIPS_ONLY = {"display": "none", _CHIPS_WIDTH: {"display": "flex"}}
_MENU_ONLY = {"display": "flex", _CHIPS_WIDTH: {"display": "none"}}


def base_url(platform: str) -> str:
    """The platform's base URL (no trailing slash), overridable by environment."""
    return os.environ.get(f"UMATERRA_URL_{platform.upper()}",
                          _DEFAULT_URLS[platform]).rstrip("/")


def href(platform: str, region: str, language) -> str:
    """Link target: the platform's Brazil (``/``) or Canada (``/canada``) page,
    carrying the language. ``language`` may be a string or a state Var.

    The portal has no regions and keeps its language in the path rather than a
    parameter: Portuguese at ``/``, then ``/es/``, ``/fr/`` and ``/en/`` (the
    default for anything else)."""
    if platform == PORTAL:
        root = base_url(PORTAL)
        return rx.match(language, ("pt", f"{root}/"), ("es", f"{root}/es/"),
                        ("fr", f"{root}/fr/"), f"{root}/en/")
    if platform == "clima":             # one page for both countries; ?region=ca frames Canada
        return (f"{base_url(platform)}/app/?lang={language}"
                + ("&region=ca" if region == "canada" else ""))
    path = "/canada" if region == "canada" else "/"
    return f"{base_url(platform)}{path}?lang={language}"


def _by_lang(table: dict, language):
    """Pick ``table[lang]`` for a language that may be a Var (English default)."""
    return rx.match(language, *[(code, table[code]) for code in _LANGS[1:]], table["en"])


def _tip(platform: str, language, here: bool):
    desc = {c: f"{NAMES[platform]} — {DESCRIPTIONS[platform][c]}" for c in _LANGS}
    if not here:
        return _by_lang(desc, language)
    return _by_lang({c: f"{desc[c]} ({HERE[c]})" for c in _LANGS}, language)


def _chip(platform: str, *, current: str, region: str, language,
          accent: str) -> rx.Component:
    here = platform == current          # never true for the portal
    inner = rx.hstack(
        rx.icon(ICONS[platform], size=14),
        rx.text(NAMES[platform], size="1", weight="medium"),
        spacing="1", align="center",
        padding="3px 9px", border_radius="var(--radius-2)",
    )
    if here:
        body = rx.box(
            inner, aria_current="page",
            background=f"var(--{accent}-4)", color=f"var(--{accent}-11)",
        )
    else:
        body = rx.link(
            rx.box(inner, color="var(--gray-11)",
                   _hover={"background": "var(--gray-4)", "color": "var(--gray-12)"}),
            href=href(platform, region, language), underline="none",
            aria_label=_tip(platform, language, here),
        )
    return rx.tooltip(body, content=_tip(platform, language, here),
                      side="bottom", delay_duration=250)


def _menu_item(platform: str, *, current: str, region: str, language) -> rx.Component:
    here = platform == current          # never true for the portal
    text = rx.vstack(
        rx.hstack(
            rx.icon(ICONS[platform], size=14),
            rx.text(NAMES[platform], size="2", weight="bold"),
            rx.cond(here, rx.badge(_by_lang(HERE, language), size="1", variant="soft"),
                    rx.fragment()),
            spacing="2", align="center",
        ),
        rx.text(_by_lang({c: DESCRIPTIONS[platform][c] for c in _LANGS}, language),
                size="1", color="var(--gray-11)", white_space="normal",
                line_height="1.4"),
        spacing="1", align_items="start",
        max_width="min(78vw, 300px)",
    )
    return rx.menu.item(
        text, disabled=here,
        on_click=rx.redirect(href(platform, region, language)),
        style={"height": "auto", "padding": "8px 10px", "cursor": "pointer"},
    )


def suite_links(current: str, *, region: str, language, accent: str = "green",
                compact: bool = False) -> rx.Component:
    """The platform switcher. ``current`` is this app (``"camposcope"``,
    ``"naturametrics"``, ``"yvynation"`` or ``"clima"``); ``region`` is ``"brazil"`` or
    ``"canada"`` — the page the reader is on, which the links preserve;
    ``language`` is the page's language (string or Var)."""
    menu = rx.menu.root(
        # The button is the trigger's *direct* child: wrapping it in a tooltip
        # here made the tooltip wrapper swallow the trigger's props, and the menu
        # never opened. The menu itself is the explanation, so a plain title does.
        rx.menu.trigger(
            rx.button(rx.icon("layout-grid", size=15),
                      rx.text("UmaTerra", display=["none", "none", "block", "block"]),
                      size="1", variant="soft", color_scheme="gray",
                      aria_label=_by_lang(TITLE, language),
                      title=_by_lang(TITLE, language)),
        ),
        rx.menu.content(
            _menu_item(PORTAL, current=current, region=region, language=language),
            rx.menu.separator(),
            *[_menu_item(p, current=current, region=region, language=language)
              for p in PLATFORMS],
            side="bottom", align="end",
        ),
    )
    if compact:
        return rx.box(menu, flex_shrink="0")
    chips = rx.hstack(
        _chip(PORTAL, current=current, region=region, language=language, accent=accent),
        # the portal is the home of the platforms that follow, not one of them
        rx.box(width="1px", height="16px", background="var(--gray-6)", margin_x="2px"),
        *[_chip(p, current=current, region=region, language=language, accent=accent)
          for p in PLATFORMS],
        role="navigation", aria_label=_by_lang(TITLE, language),
        spacing="1", align="center", flex_shrink="0",
        padding="2px", border="1px solid var(--gray-5)", border_radius="var(--radius-3)",
    )
    return rx.fragment(
        rx.box(chips, style=_CHIPS_ONLY, flex_shrink="0"),
        rx.box(menu, style=_MENU_ONLY, flex_shrink="0"),
    )
