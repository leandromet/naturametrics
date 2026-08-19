"""Sidebar controls for the map layers.

Basemap, the MapBiomas year/opacity controls, the change mask, the IFN
conglomerado grid with its four filters, and the IBGE biome overlay. The year
slider is the acceptance test for decision D1 — moving it must repaint the layer
without the map viewport shifting.
"""

from __future__ import annotations

import reflex as rx

from ..config import datasets as ds
from ..config import mapbiomas as mb
from ..config import settings as st
from ..services import change_mask as cm
from ..state import AppState


def _section(title: str, *children) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="1", weight="bold", color_scheme="gray",
                style={"textTransform": "uppercase", "letterSpacing": "0.06em"}),
        *children,
        spacing="2",
        align_items="stretch",
        width="100%",
    )


#: Notes shown under the select, keyed by basemap. Only the Earth Engine ones
#: need explaining — a partial mosaic looks broken until you know it is partial.
_BASEMAP_NOTES = {k: v["note_pt"] for k, v in ds.EE_BASEMAPS.items()}


def basemap_control() -> rx.Component:
    labels = {k: v["label_pt"] for k, v in ds.ALL_BASEMAPS.items()}
    return _section(
        "Mapa base",
        rx.select(
            list(labels.values()),
            value=rx.Var.create(labels)[AppState.basemap],
            on_change=lambda label: AppState.set_basemap(
                rx.Var.create({v: k for k, v in labels.items()})[label]
            ),
            width="100%",
        ),
        rx.cond(
            rx.Var.create(_BASEMAP_NOTES).contains(AppState.basemap),
            rx.text(rx.Var.create(_BASEMAP_NOTES)[AppState.basemap],
                    size="1", color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.basemap_error != "",
            rx.callout(AppState.basemap_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.fragment(),
        ),
    )


def mapbiomas_control() -> rx.Component:
    return _section(
        "Cobertura do solo",
        rx.hstack(
            rx.switch(
                checked=AppState.show_mapbiomas,
                on_change=AppState.toggle_mapbiomas,
            ),
            rx.text("MapBiomas 10.1", size="2"),
            rx.spacer(),
            rx.cond(
                AppState.layer_busy,
                rx.spinner(size="1"),
                rx.fragment(),
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        rx.cond(
            AppState.show_mapbiomas,
            rx.vstack(
                rx.hstack(
                    rx.text("Ano", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.mapbiomas_year.to_string(),
                             color_scheme="green", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=mb.MAPBIOMAS_YEAR_START,
                    max=mb.MAPBIOMAS_YEAR_END,
                    step=1,
                    default_value=[mb.MAPBIOMAS_YEAR_END],
                    on_change=AppState.set_mapbiomas_year,
                    width="100%",
                ),
                rx.hstack(
                    rx.text(str(mb.MAPBIOMAS_YEAR_START), size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(str(mb.MAPBIOMAS_YEAR_END), size="1", color_scheme="gray"),
                    width="100%",
                ),
                rx.hstack(
                    rx.text(
                        rx.cond(
                            AppState.compare_enabled,
                            "Opacidade — ano à direita",
                            "Opacidade",
                        ),
                        size="1", color_scheme="gray",
                    ),
                    rx.spacer(),
                    rx.text(AppState.opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5,
                    default_value=[75],
                    on_change=AppState.set_mapbiomas_opacity,
                    width="100%",
                ),
                spacing="2",
                width="100%",
                padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def buffer_preview_control() -> rx.Component:
    """MapBiomas shown only inside the buffer of the point under the cursor."""
    return _section(
        "Uso no buffer",
        rx.hstack(
            rx.switch(checked=AppState.show_buffer_preview,
                      on_change=AppState.toggle_buffer_preview),
            rx.text("Mostrar Uso no Buffer", size="2"),
            rx.spacer(),
            rx.badge(f"{st.BUFFER_PREVIEW_RADIUS_KM:g} km", size="1",
                     variant="soft", color_scheme="gray"),
            width="100%", align="center", spacing="2",
        ),
        rx.text(
            "Ao passar o cursor sobre um conglomerado — ou ao escolher um ponto "
            "— o MapBiomas aparece só dentro do raio de análise, no ano "
            "selecionado acima. Não consulta o Earth Engine: usa os mesmos "
            "blocos já pré-carregados.",
            size="1", color_scheme="gray",
        ),
        rx.cond(
            AppState.show_mapbiomas,
            rx.text(
                "Oculta enquanto «MapBiomas 10.1» está ligado — a cobertura já "
                "aparece no mapa inteiro.",
                size="1", color_scheme="amber",
            ),
            rx.fragment(),
        ),
    )


def compare_control() -> rx.Component:
    """Two MapBiomas years at once, split by a draggable vertical divider."""
    return _section(
        "Comparar dois anos",
        rx.hstack(
            rx.switch(checked=AppState.compare_enabled,
                      on_change=AppState.toggle_compare),
            rx.text("Cortina deslizante", size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.compare_enabled,
            rx.vstack(
                rx.hstack(
                    rx.text("Ano à esquerda", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.compare_year.to_string(),
                             color_scheme="amber", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=mb.MAPBIOMAS_YEAR_START, max=mb.MAPBIOMAS_YEAR_END, step=1,
                    default_value=[cm.FOREST_CODE_BASELINE_YEAR],
                    on_change=AppState.set_compare_year, width="100%",
                ),
                rx.hstack(
                    rx.text("Opacidade — ano à esquerda", size="1",
                            color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.compare_opacity_pct.to_string() + "%",
                            size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5,
                    default_value=[75],
                    on_change=AppState.set_compare_opacity,
                    width="100%",
                ),
                rx.text(
                    "Arraste a linha branca no mapa. À direita fica o ano "
                    "selecionado acima em «Cobertura do solo».",
                    size="1", color_scheme="gray",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def change_mask_control() -> rx.Component:
    """Natural vegetation lost or regrown since the Forest Code baseline."""
    return _section(
        "Mudança na vegetação natural",
        rx.hstack(
            rx.switch(checked=AppState.show_change_mask,
                      on_change=AppState.toggle_change_mask),
            rx.text("Candidatos a recuperação", size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_change_mask,
            rx.vstack(
                rx.hstack(
                    rx.text("Ano base", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.change_from_year.to_string(),
                             color_scheme="red", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=mb.MAPBIOMAS_YEAR_START, max=mb.MAPBIOMAS_YEAR_END - 1, step=1,
                    default_value=[cm.FOREST_CODE_BASELINE_YEAR],
                    on_change=AppState.set_change_from_year, width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=cm.CHANGE_COLORS[cm.CHANGE_LOSS]),
                    rx.text("Perda de vegetação natural", size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=cm.CHANGE_COLORS[cm.CHANGE_GAIN]),
                    rx.text("Regeneração", size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.callout(
                    "2008 é o marco do Código Florestal: vegetação nativa suprimida "
                    "depois dessa data tem obrigação de recomposição. Esta camada é "
                    "uma triagem, não um laudo — não considera CAR, APP/RL, porte do "
                    "imóvel nem autorizações.",
                    icon="info", size="1", color_scheme="gray", width="100%",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def _filter_select(label: str, options, value, on_change,
                   disabled=False) -> rx.Component:
    """One row of the IFN filter cascade."""
    return rx.vstack(
        rx.text(label, size="1", color_scheme="gray"),
        rx.select(
            options,
            value=value,
            on_change=on_change,
            disabled=disabled,
            width="100%",
            size="2",
        ),
        spacing="1",
        width="100%",
        align_items="stretch",
    )


def ifn_control() -> rx.Component:
    """The IFN conglomerado grid, filtered by região / estado / município / bioma.

    The counter is not decoration: with 17 479 points nationwide, the difference
    between a filter that selected 140 points and one that selected none is
    invisible on the map until you zoom to the right place.
    """
    return _section(
        "Inventário Florestal Nacional",
        rx.hstack(
            rx.switch(checked=AppState.show_ifn, on_change=AppState.toggle_ifn),
            rx.text("Conglomerados", size="2"),
            rx.spacer(),
            rx.cond(AppState.ifn_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_ifn,
            rx.vstack(
                _filter_select("Região", AppState.ifn_region_options,
                               AppState.ifn_region_value,
                               AppState.set_ifn_region),
                _filter_select("Bioma", AppState.ifn_biome_options,
                               AppState.ifn_biome_value,
                               AppState.set_ifn_biome),
                _filter_select("Estado", AppState.ifn_uf_options,
                               AppState.ifn_uf_value, AppState.set_ifn_uf),
                _filter_select("Município", AppState.ifn_municipality_options,
                               AppState.ifn_municipality_value,
                               AppState.set_ifn_municipality,
                               disabled=AppState.ifn_uf == ""),
                rx.cond(
                    AppState.ifn_municipality_hint != "",
                    rx.text(AppState.ifn_municipality_hint, size="1",
                            color_scheme="gray"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.badge(AppState.ifn_count_label, color_scheme="jade",
                             variant="soft"),
                    rx.spacer(),
                    rx.cond(
                        AppState.ifn_has_filter,
                        rx.button(
                            rx.icon("rotate-ccw", size=12),
                            "Limpar",
                            size="1", variant="ghost",
                            on_click=AppState.clear_ifn_filters,
                        ),
                        rx.fragment(),
                    ),
                    width="100%", align="center",
                ),
                rx.cond(
                    AppState.ifn_count == 0,
                    rx.callout(
                        "Nenhum conglomerado nesta combinação de filtros.",
                        icon="info", size="1", color_scheme="amber", width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def _multi_row(row: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(row["conglomerado"], size="1", weight="medium",
                style={"whiteSpace": "nowrap"}),
        rx.text(row["place"], size="1", color_scheme="gray", flex="1",
                no_of_lines=1),
        rx.text(row["pending"], size="1", color_scheme="gray"),
        spacing="2", align="center", width="100%",
    )


def multi_select_control() -> rx.Component:
    """Pick many conglomerados and read them as one landscape."""
    return _section(
        "Seleção múltipla",
        rx.hstack(
            rx.switch(checked=AppState.multi_mode,
                      on_change=AppState.toggle_multi_mode),
            rx.text("Somar vários conglomerados", size="2"),
            rx.spacer(),
            rx.cond(
                AppState.multi_progress != "",
                rx.text(AppState.multi_progress, size="1", color_scheme="gray"),
                rx.fragment(),
            ),
            rx.cond(AppState.multi_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.multi_mode,
            rx.vstack(
                rx.text(
                    "Clique nos conglomerados para incluir ou remover, ou "
                    "segure Ctrl (Cmd no Mac) e arraste para selecionar uma "
                    "área inteira. O gráfico passa a mostrar a soma das áreas "
                    "de cada raio. Shift+arrastar continua sendo o zoom por "
                    "área do mapa, e cliques avulsos ficam desativados enquanto "
                    "o modo está ligado.",
                    size="1", color_scheme="gray", style={"lineHeight": "1.4"},
                ),
                rx.hstack(
                    rx.badge(AppState.multi_label, color_scheme="jade",
                             variant="soft", size="1"),
                    rx.spacer(),
                    rx.cond(
                        AppState.multi_count > 0,
                        rx.button(
                            rx.icon("rotate-ccw", size=12), "Limpar",
                            size="1", variant="ghost",
                            on_click=AppState.clear_multi_selection,
                        ),
                        rx.fragment(),
                    ),
                    width="100%", align="center",
                ),
                rx.cond(
                    AppState.multi_error != "",
                    rx.callout(AppState.multi_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    AppState.multi_count > 0,
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(AppState.multi_points, _multi_row),
                            spacing="1", width="100%",
                        ),
                        type="auto", scrollbars="vertical",
                        style={"maxHeight": "150px"},
                    ),
                    rx.fragment(),
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def _biome_legend() -> rx.Component:
    """One swatch per biome, in the same order and the same hues the map draws."""
    conf = ds.IBGE_BIOME_DOMAIN
    return rx.vstack(
        *[
            rx.hstack(
                rx.box(width="10px", height="10px", border_radius="2px",
                       background=f"#{conf['palette'][name]}"),
                rx.text(name, size="1"),
                spacing="2", align="center", width="100%",
            )
            for name in conf["biomes"]
        ],
        spacing="1", width="100%",
    )


def biome_control() -> rx.Component:
    return _section(
        "Biomas (IBGE)",
        rx.hstack(
            rx.switch(checked=AppState.show_biomes,
                      on_change=AppState.toggle_biomes),
            rx.text("Biomas e domínios", size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_biomes,
            rx.vstack(
                rx.hstack(
                    rx.text("Opacidade", size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.biome_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=80, step=5,
                    default_value=[35],
                    on_change=AppState.set_biome_opacity,
                    width="100%",
                ),
                _biome_legend(),
                rx.text(
                    "Passe o cursor sobre um polígono para ver bioma, domínio "
                    "fitogeográfico e região natural. Os limites estão "
                    "simplificados (~1 km) para desenho no navegador.",
                    size="1", color_scheme="gray",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def status_line() -> rx.Component:
    return rx.hstack(
        rx.cond(
            AppState.ee_error != "",
            rx.icon("triangle-alert", size=14, color="var(--red-9)"),
            rx.cond(
                AppState.ee_ready,
                rx.icon("circle-check", size=14, color="var(--green-9)"),
                rx.spinner(size="1"),
            ),
        ),
        rx.text(AppState.ee_status_label, size="1", color_scheme="gray"),
        spacing="2",
        align="center",
        width="100%",
    )


def point_control() -> rx.Component:
    """The clicked location. Phase 1 hangs the buffer analysis off this panel."""
    return _section(
        "Ponto de estudo",
        rx.cond(
            AppState.has_point,
            rx.vstack(
                rx.hstack(
                    rx.icon("map-pin", size=14, color="var(--jade-11)"),
                    rx.text(AppState.point_label, size="2", weight="medium"),
                    spacing="2", align="center",
                ),
                rx.text("Clique no mapa para escolher outro ponto.",
                        size="1", color_scheme="gray"),
                spacing="1", align_items="start", width="100%",
            ),
            rx.cond(
                AppState.point_error != "",
                rx.callout(AppState.point_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.text("Clique no mapa para escolher um ponto.",
                        size="1", color_scheme="gray"),
            ),
        ),
    )


def layer_panel() -> rx.Component:
    return rx.vstack(
        point_control(),
        rx.divider(),
        basemap_control(),
        rx.divider(),
        mapbiomas_control(),
        rx.divider(),
        buffer_preview_control(),
        rx.divider(),
        compare_control(),
        rx.divider(),
        change_mask_control(),
        rx.divider(),
        multi_select_control(),
        rx.divider(),
        ifn_control(),
        rx.divider(),
        biome_control(),
        rx.spacer(),
        rx.divider(),
        status_line(),
        rx.cond(
            AppState.ee_error != "",
            rx.callout(
                AppState.ee_error,
                icon="triangle-alert",
                color_scheme="red",
                size="1",
                width="100%",
            ),
            rx.fragment(),
        ),
        spacing="4",
        align_items="stretch",
        height="100%",
        width="100%",
        padding="1rem",
    )
