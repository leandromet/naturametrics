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
from ..services.biomass import AGB_YEARS
from ..state import AppState
from .user_points import enviar_dados_dialog


def _info_icon(text: rx.Var | str) -> rx.Component:
    """A tap/click affordance, not a hover tooltip — this app is mobile-first
    throughout (the viewport meta tag in naturametrics.py, responsive
    breakpoints on every section here), and hover has no equivalent on touch.
    """
    return rx.popover.root(
        rx.popover.trigger(
            rx.icon_button(
                rx.icon("info", size=12),
                size="1", variant="ghost", color_scheme="gray",
                aria_label=text,
            ),
        ),
        rx.popover.content(
            rx.text(text, size="1", style={"lineHeight": "1.4"}),
            max_width="260px",
        ),
    )


def _section(title: str, *children, info: rx.Var | str | None = None) -> rx.Component:
    header = rx.text(title, size="1", weight="bold", color_scheme="gray",
                     style={"textTransform": "uppercase", "letterSpacing": "0.06em"})
    return rx.vstack(
        rx.hstack(header, _info_icon(info), spacing="1", align="center")
        if info is not None else header,
        *children,
        spacing="2",
        align_items="stretch",
        width="100%",
    )


def _group(value: str, icon: str, title, *sections: rx.Component) -> rx.Component:
    """One collapsible cluster of related `_section()` controls — the
    sidebar's top-level grouping (``layer_panel()``), one level up from the
    per-control accordion `ifn_control()` already used for its own filter
    grid. `variant="surface"` (a bordered card per group) rather than that
    inner accordion's `"ghost"`, so the grouping itself reads as a visible
    boundary, not just another divider in the same flat list — the whole
    point of grouping 16 previously-flat sections was to make the sidebar
    scannable at a glance, which a border does and a plain divider does not.
    A divider is still placed between the sections *within* one group, same
    as the flat list always had.
    """
    body = []
    for i, section in enumerate(sections):
        if i:
            body.append(rx.divider())
        body.append(section)
    return rx.accordion.item(
        rx.accordion.header(
            rx.accordion.trigger(
                rx.hstack(
                    rx.icon(icon, size=15),
                    rx.text(title, size="2", weight="bold"),
                    spacing="2", align="center",
                ),
            ),
        ),
        rx.accordion.content(
            rx.vstack(*body, spacing="3", width="100%", padding_top="0.25rem"),
            # Radix's own AccordionContent bakes in
            # `padding_x: var(--space-4)` (16px) on top of this panel's own
            # root `padding="1rem"` — 32px of inset instead of 16px is a lot
            # to give up on a ~320px sidebar, and it made every section
            # inside a group read as squeezed relative to the group's own
            # trigger row.
            padding_x="0",
        ),
        value=value,
    )


def basemap_control() -> rx.Component:
    return _section(
        AppState.tr["section_basemap"],
        rx.select(
            AppState.basemap_options,
            value=AppState.basemap_label,
            on_change=AppState.set_basemap_by_label,
            width="100%",
        ),
        rx.cond(
            AppState.basemap_note != "",
            rx.text(AppState.basemap_note, size="1", color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.basemap_error != "",
            rx.callout(AppState.basemap_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.fragment(),
        ),
        info=AppState.tr["basemap_info"],
    )


def mapbiomas_control() -> rx.Component:
    return _section(
        AppState.tr["section_landcover"],
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
                    rx.text(AppState.tr["year_label"], size="1", color_scheme="gray"),
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
                            AppState.compare_mode == "years",
                            AppState.tr["opacity_label_compare"],
                            AppState.tr["opacity_label"],
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
        info=AppState.tr["mapbiomas_info"],
    )


def compare_control() -> rx.Component:
    """One swipe divider, several possible pairings: two MapBiomas years,
    IBGE Vegetação 2022 vs. MapBiomas 2022, the two SPOT 2008 mosaics
    against each other (Visual vs. false-colour NIR), or MapBiomas
    2008/IBGE checked against either SPOT 2008 band — validating a
    classification straight against the Forest Code's reference-year
    imagery. See state/_layers.py's set_compare_mode and
    SPOT_COMPARE_SIDES. A single select replaces what used to be two
    separate always-visible sections (compare_control/ibge_compare_control)
    that only knew about each other enough to turn one another off.
    """
    return _section(
        AppState.tr["section_compare"],
        rx.hstack(
            rx.select(
                AppState.compare_mode_options,
                value=AppState.compare_mode_label,
                on_change=AppState.set_compare_mode_by_label,
                width="100%",
            ),
            rx.cond(AppState.layer_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.compare_mode == "years",
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["compare_year_left"], size="1",
                            color_scheme="gray"),
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
                    rx.text(AppState.tr["compare_opacity_left"], size="1",
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
                    AppState.tr["compare_note"],
                    size="1", color_scheme="gray",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        rx.cond(
            AppState.compare_mode == "ibge",
            rx.text(AppState.tr["ibge_compare_note"], size="1",
                    color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.compare_mode == "spot",
            rx.text(AppState.tr["spot_compare_note"], size="1",
                    color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.compare_mode == "mb_spot_visual",
            rx.text(AppState.tr["mb_spot_visual_note"], size="1",
                    color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.compare_mode == "mb_spot_analytic",
            rx.text(AppState.tr["mb_spot_analytic_note"], size="1",
                    color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.compare_mode == "ibge_spot_visual",
            rx.text(AppState.tr["ibge_spot_visual_note"], size="1",
                    color_scheme="gray"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.compare_mode == "ibge_spot_analytic",
            rx.text(AppState.tr["ibge_spot_analytic_note"], size="1",
                    color_scheme="gray"),
            rx.fragment(),
        ),
        info=AppState.tr["compare_info"],
    )


def change_mask_control() -> rx.Component:
    """Natural vegetation lost or regrown since the Forest Code baseline."""
    return _section(
        AppState.tr["section_change_mask"],
        rx.hstack(
            rx.switch(checked=AppState.show_change_mask,
                      on_change=AppState.toggle_change_mask),
            rx.text(AppState.tr["change_mask_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_change_mask,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["change_base_year"], size="1",
                            color_scheme="gray"),
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
                    rx.text(AppState.tr["change_loss_label"], size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=cm.CHANGE_COLORS[cm.CHANGE_GAIN]),
                    rx.text(AppState.tr["change_gain_label"], size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.callout(
                    AppState.tr["change_mask_callout"],
                    icon="info", size="1", color_scheme="gray", width="100%",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["change_mask_info"],
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
        AppState.tr["section_ifn"],
        rx.hstack(
            rx.switch(checked=AppState.show_ifn, on_change=AppState.toggle_ifn),
            rx.text(AppState.tr["ifn_toggle_label"], size="2"),
            rx.spacer(),
            rx.cond(AppState.ifn_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_ifn,
            rx.vstack(
                rx.accordion.root(
                    rx.accordion.item(
                        rx.accordion.header(
                            rx.accordion.trigger(
                                rx.hstack(
                                    rx.icon("list-filter", size=13),
                                        rx.text(AppState.tr["ifn_filters_title"],
                                            size="2", weight="medium"),
                                    spacing="2", align="center",
                                ),
                            ),
                        ),
                        rx.accordion.content(
                            rx.vstack(
                                _filter_select(AppState.tr["filter_region"],
                                               AppState.ifn_region_options,
                                               AppState.ifn_region_value,
                                               AppState.set_ifn_region),
                                _filter_select(AppState.tr["filter_biome"],
                                               AppState.ifn_biome_options,
                                               AppState.ifn_biome_value,
                                               AppState.set_ifn_biome),
                                _filter_select(AppState.tr["filter_uf"],
                                               AppState.ifn_uf_options,
                                               AppState.ifn_uf_value,
                                               AppState.set_ifn_uf),
                                _filter_select(AppState.tr["filter_municipality"],
                                               AppState.ifn_municipality_options,
                                               AppState.ifn_municipality_value,
                                               AppState.set_ifn_municipality,
                                               disabled=AppState.ifn_uf == ""),
                                rx.cond(
                                    AppState.ifn_municipality_hint != "",
                                    rx.text(AppState.ifn_municipality_hint, size="1",
                                            color_scheme="gray"),
                                    rx.fragment(),
                                ),
                                spacing="2", width="100%",
                            ),
                        ),
                        value="filters",
                    ),
                    type="single",
                    collapsible=True,
                    variant="ghost",
                    width="100%",
                ),
                rx.hstack(
                    rx.badge(AppState.ifn_count_label, color_scheme="jade",
                             variant="soft"),
                    rx.spacer(),
                    rx.cond(
                        AppState.ifn_has_filter,
                        rx.button(
                            rx.icon("rotate-ccw", size=12),
                            AppState.tr["clear_button"],
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
                        AppState.tr["ifn_empty_callout"],
                        icon="info", size="1", color_scheme="amber", width="100%",
                    ),
                    rx.fragment(),
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["ifn_info"],
    )


def embargos_control() -> rx.Component:
    """IBAMA embargos — a live third-party feed, fetched by the
    browser per-viewport (services.embargos), not minted by Earth Engine —
    so unlike mapbiomas_control/biomass_control there is no layer_busy
    spinner tied to this toggle, same reasoning as biome_control."""
    return _section(
        AppState.tr["section_embargos"],
        rx.hstack(
            rx.switch(checked=AppState.show_embargos,
                      on_change=AppState.toggle_embargos),
            rx.text(AppState.tr["embargos_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_embargos,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.embargos_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5,
                    default_value=[70],
                    on_change=AppState.set_embargos_opacity,
                    width="100%",
                ),
                rx.text(AppState.tr["embargos_note"], size="1", color_scheme="gray"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["embargos_info"],
    )


def auto_infracao_control() -> rx.Component:
    """IBAMA autos de infração — a second live third-party feed, same
    mechanism as embargos_control right above it, but far denser (709 803
    points nationwide vs. embargos' 91 120 polygons), hence the higher
    min_zoom the layer gates itself behind (services.auto_infracao)."""
    return _section(
        AppState.tr["section_auto_infracao"],
        rx.hstack(
            rx.switch(checked=AppState.show_auto_infracao,
                      on_change=AppState.toggle_auto_infracao),
            rx.text(AppState.tr["auto_infracao_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_auto_infracao,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.auto_infracao_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5,
                    default_value=[85],
                    on_change=AppState.set_auto_infracao_opacity,
                    width="100%",
                ),
                rx.text(AppState.tr["auto_infracao_note"], size="1", color_scheme="gray"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["auto_infracao_info"],
    )


def user_points_control() -> rx.Component:
    """A pasted coordinate list, standing in for the IFN grid while active.

    Kept as its own section rather than folded into ifn_control(): the two are
    alternatives, not variants of one thing, and IFN's four filters have no
    meaning here.
    """
    return _section(
        AppState.tr["section_user_points"],
        rx.hstack(
            enviar_dados_dialog(),
            rx.spacer(),
            rx.cond(
                AppState.user_points_active,
                rx.badge(AppState.user_points_count, color_scheme="iris",
                         variant="soft"),
                rx.fragment(),
            ),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.user_points_active,
            rx.hstack(
                rx.text(
                    AppState.tr["user_points_active_note"],
                    size="1", color_scheme="gray", flex="1",
                ),
                rx.button(
                    rx.icon("rotate-ccw", size=12), AppState.tr["reset_button"],
                    size="1", variant="ghost",
                    on_click=AppState.reset_user_points,
                ),
                width="100%", align="center",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["user_points_info"],
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
        AppState.tr["section_multi_select"],
        rx.hstack(
            rx.switch(checked=AppState.multi_mode,
                      on_change=AppState.toggle_multi_mode),
            rx.text(AppState.tr["multi_toggle_label"], size="2"),
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
                    AppState.tr["multi_help_text"],
                    size="1", color_scheme="gray", style={"lineHeight": "1.4"},
                ),
                rx.hstack(
                    rx.badge(AppState.multi_label, color_scheme="jade",
                             variant="soft", size="1"),
                    rx.spacer(),
                    rx.cond(
                        AppState.multi_count > 0,
                        rx.button(
                            rx.icon("rotate-ccw", size=12), AppState.tr["clear_button"],
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
        info=AppState.tr["multi_select_info"],
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
        AppState.tr["section_biomes"],
        rx.hstack(
            rx.switch(checked=AppState.show_biome_labels,
                      on_change=AppState.toggle_biome_labels),
            rx.text(AppState.tr["biomes_labels_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.hstack(
            rx.switch(checked=AppState.show_biomes,
                      on_change=AppState.toggle_biomes),
            rx.text(AppState.tr["biomes_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_biomes,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.biome_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=80, step=5,
                    default_value=[55],
                    on_change=AppState.set_biome_opacity,
                    width="100%",
                ),
                _biome_legend(),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["biomes_info"],
    )


def biomass_control() -> rx.Component:
    """ESA CCI Biomass_cci above-ground biomass — a discrete set of ten
    years (2007, 2010, 2015-2022), not the continuous range MapBiomas'
    slider assumes, so the slider here moves over an *index* into that list
    (state.set_biomass_year_index) rather than the year number itself."""
    return _section(
        AppState.tr["section_biomass"],
        rx.hstack(
            rx.switch(checked=AppState.show_biomass,
                      on_change=AppState.toggle_biomass),
            rx.text("ESA CCI Biomass v6.0", size="2"),
            rx.spacer(),
            rx.cond(AppState.layer_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_biomass,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["year_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.biomass_year.to_string(),
                             color_scheme="green", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=len(AGB_YEARS) - 1, step=1,
                    default_value=[len(AGB_YEARS) - 1],
                    on_change=AppState.set_biomass_year_index,
                    width="100%",
                ),
                rx.hstack(
                    rx.text(str(AGB_YEARS[0]), size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(str(AGB_YEARS[-1]), size="1", color_scheme="gray"),
                    width="100%",
                ),
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.biomass_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5, default_value=[75],
                    on_change=AppState.set_biomass_opacity,
                    width="100%",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["biomass_info"],
    )


def ibge_vegetation_control() -> rx.Component:
    """IBGE Vegetação 2022 — a single 1:250.000 snapshot, so unlike
    ``biomass_control`` there is no year slider, just a toggle and opacity."""
    return _section(
        AppState.tr["section_ibge_veg"],
        rx.hstack(
            rx.switch(checked=AppState.show_ibge_veg,
                      on_change=AppState.toggle_ibge_veg),
            rx.text("IBGE Vegetação 2022", size="2"),
            rx.spacer(),
            rx.cond(AppState.layer_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_ibge_veg,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.ibge_veg_opacity_pct.to_string() + "%", size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5, default_value=[60],
                    on_change=AppState.set_ibge_veg_opacity,
                    width="100%",
                ),
                rx.text(AppState.tr["ibge_veg_layer_note"], size="1", color_scheme="gray"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        info=AppState.tr["ibge_veg_info"],
    )




def hansen_control() -> rx.Component:
    """Hansen Global Forest Change, ported from the Canada page — same
    asset, same visualization (config.datasets.HANSEN_GFC), so the two
    pages agree on what a "forest" pixel is. Two independent sub-layers
    (tree cover 2000, loss/gain) share one canopy-cover threshold slider,
    which sits outside both toggles because it governs both."""
    return _section(
        AppState.tr["section_forest_change"],
        rx.hstack(
            rx.switch(checked=AppState.show_hansen_treecover,
                      on_change=AppState.toggle_hansen_treecover),
            rx.text(AppState.tr["hansen_treecover_toggle"], size="2"),
            rx.spacer(),
            rx.cond(AppState.layer_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_hansen_treecover,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.hansen_treecover_opacity_pct.to_string() + "%",
                            size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5, default_value=[60],
                    on_change=AppState.set_hansen_treecover_opacity,
                    width="100%",
                ),
                spacing="1", width="100%",
            ),
            rx.fragment(),
        ),
        rx.hstack(
            rx.switch(checked=AppState.show_hansen_change,
                      on_change=AppState.toggle_hansen_change),
            rx.text(AppState.tr["hansen_change_toggle"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.show_hansen_change,
            rx.vstack(
                rx.hstack(
                    rx.text(AppState.tr["change_base_year"], size="1",
                            color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(AppState.hansen_change_from_year.to_string(),
                             color_scheme="red", variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=ds.HANSEN_GFC["loss_year_start"],
                    max=ds.HANSEN_GFC["loss_year_end"], step=1,
                    default_value=[ds.HANSEN_GFC["loss_year_start"]],
                    on_change=AppState.set_hansen_change_from_year,
                    width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=ds.HANSEN_GFC["loss_color"]),
                    rx.text(AppState.tr["hansen_loss_label"], size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=ds.HANSEN_GFC["gain_color"]),
                    rx.text(AppState.tr["hansen_gain_label"], size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.text(AppState.tr["opacity_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(AppState.hansen_change_opacity_pct.to_string() + "%",
                            size="1"),
                    width="100%",
                ),
                rx.slider(
                    min=0, max=100, step=5, default_value=[85],
                    on_change=AppState.set_hansen_change_opacity,
                    width="100%",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        # Governs both sub-layers above, so it sits outside either toggle.
        rx.hstack(
            rx.text(AppState.tr["hansen_threshold_label"], size="1", color_scheme="gray"),
            rx.spacer(),
            rx.text(AppState.hansen_treecover_threshold.to_string() + "%", size="1"),
            width="100%",
        ),
        rx.slider(
            min=0, max=90, step=5, default_value=[st.HANSEN_TREECOVER_THRESHOLD],
            on_change=AppState.set_hansen_treecover_threshold,
            width="100%",
        ),
        info=AppState.tr["hansen_info"],
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
        AppState.tr["section_point"],
        rx.vstack(
            rx.cond(
                AppState.has_point,
                rx.hstack(
                    rx.icon("map-pin", size=14, color="var(--jade-11)"),
                    rx.text(AppState.point_label, size="2", weight="medium"),
                    spacing="2", align="center",
                ),
                rx.cond(
                    AppState.point_error != "",
                    rx.callout(AppState.point_error, icon="triangle-alert",
                               color_scheme="amber", size="1", width="100%"),
                    rx.text(AppState.tr["point_click_choose"],
                            size="1", color_scheme="gray"),
                ),
            ),
            rx.cond(
                AppState.has_point,
                rx.text(AppState.tr["point_click_other"],
                        size="1", color_scheme="gray"),
                rx.fragment(),
            ),
            rx.hstack(
                rx.switch(
                    checked=AppState.buffer_shape == "square",
                    on_change=AppState.toggle_buffer_shape,
                    disabled=AppState.multi_active,
                ),
                rx.text(AppState.tr["buffer_square_toggle_label"], size="1"),
                spacing="2", align="center",
            ),
            rx.hstack(
                rx.switch(checked=AppState.show_buffer_preview,
                          on_change=AppState.toggle_buffer_preview),
                rx.text(AppState.tr["buffer_preview_toggle_label"], size="1"),
                rx.spacer(),
                rx.badge(f"{st.BUFFER_PREVIEW_RADIUS_KM:g} km", size="1",
                         variant="soft", color_scheme="gray"),
                width="100%", align="center", spacing="2",
            ),
            rx.cond(
                AppState.show_mapbiomas,
                rx.text(
                    AppState.tr["buffer_preview_hidden_note"],
                    size="1", color_scheme="amber",
                ),
                rx.fragment(),
            ),
            spacing="1", align_items="start", width="100%",
        ),
        info=AppState.tr["point_info"],
    )


def geometry_control() -> rx.Component:
    """The draw toolbar's arm/disarm switch, plus a status readout for
    whatever it (or the WKT/KML tabs of "Enviar dados") last produced.

    The switch matters, not just for discoverability: while it is off, a
    plain map click keeps picking a point exactly as it always has, and the
    on-map toolbar's buttons are not even shown. Arming it is what tells the
    map "the next click/drag is a shape, not a point" — see leaflet_map.js's
    drawEnabledRef for the click-suppression this drives.
    """
    return _section(
        AppState.tr["section_geometry"],
        rx.hstack(
            rx.switch(checked=AppState.draw_mode,
                      on_change=AppState.toggle_draw_mode),
            rx.text(AppState.tr["geometry_draw_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.has_geometry,
            rx.hstack(
                rx.icon("shapes", size=14, color="var(--jade-11)"),
                rx.text(AppState.point_label, size="2", weight="medium", flex="1"),
                rx.button(
                    rx.icon("rotate-ccw", size=12), AppState.tr["clear_button"],
                    size="1", variant="ghost",
                    on_click=AppState.clear_geometry,
                ),
                spacing="2", align="center", width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            AppState.geometry_error != "",
            rx.callout(AppState.geometry_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.fragment(),
        ),
        info=AppState.tr["geometry_info"],
    )


def layer_panel(fill_height: bool = True) -> rx.Component:
    """``fill_height=True`` (the desktop sidebar's own call, ``pages/
    index.py::index()``) is correct there because this panel is the ONLY
    child of that box, which is itself ``height="100%", overflow_y="auto"``
    — stretching to match just lets `rx.spacer()` push `status_line()` to
    the bottom instead of leaving a gap.

    ``fill_height=False`` is required from `_mobile_sheet()`: there, this
    panel SHARES its scrolling box with `results_drawer()` below it, both
    inside one `overflow_y="auto"` container. `height="100%"` there claimed
    100% of that shared box for this panel alone — every real bug report
    of "the sidebar/results overlap on mobile" traced back to exactly this:
    the panel's actual content (5 groups) is far taller than 100% of the
    shared box, so with the default `overflow: visible` it spilled out
    past its own claimed height rather than growing to fit, and
    `results_drawer()` — sized by normal document flow, which only reserves
    space for this panel's CLAIMED height, not its overflowing content —
    started rendering right where this panel's box ended, landing on top of
    whatever of its content had spilled past that point. `height="auto"`
    (this panel's natural content height) is what lets the shared box's
    total scrollHeight — and therefore where `results_drawer()` actually
    starts — account for the whole thing.
    """
    # Imported here, not at module level: search.py imports _section/
    # _info_icon back from this module, and a top-level import in both
    # directions would try to read them off a layer_panel module that has
    # not finished defining them yet.
    from .search import search_panel

    return rx.vstack(
        rx.accordion.root(
            rx.accordion.item(
                rx.accordion.header(
                    rx.accordion.trigger(
                        rx.hstack(
                            rx.icon("panel-left", size=15),
                            rx.text(AppState.tr["drawer_title"], size="2",
                                   weight="bold"),
                            spacing="2", align="center",
                        ),
                    ),
                ),
                rx.accordion.content(
                    _all_groups(search_panel()),
                    # See `_group()`'s own comment on why this needs
                    # `padding_x="0"` — Radix's AccordionContent otherwise
                    # bakes in its own 16px on top of this panel's root
                    # `padding="1rem"`.
                    padding_x="0",
                ),
                value="all_layers",
            ),
            type="single",
            collapsible=True,
            variant="ghost",
            width="100%",
            # Open by default: this wrapper only exists to let someone
            # collapse the whole sidebar down to one line when they want
            # maximum map space, not to hide it on a first visit — the five
            # groups inside it already start closed on their own (see
            # `_all_groups()`), which is where the actual first-visit
            # decluttering happens.
            default_value="all_layers",
        ),
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
        height="100%" if fill_height else "auto",
        width="100%",
        padding="1rem",
        # Every control in this panel uses text size="1"/"2" (Radix's
        # --font-size-1/2, 12px/14px by default) — redefining the tokens
        # here, once, at the panel root, shrinks every one of them by 3px
        # (~2.25pt) without touching each individual rx.text call, and stays
        # correct if the app's theme scaling ever changes since it's relative
        # to the inherited value, not a hard-coded px number.
        style={
            "--font-size-1": "calc(var(--font-size-1) - 3px)",
            "--font-size-2": "calc(var(--font-size-2) - 3px)",
        },
    )


def _all_groups(search_panel: rx.Component) -> rx.Component:
    """The five topic groups, each independently collapsible
    (`type="multiple"`) — nested inside `layer_panel()`'s own outer,
    single-item accordion (the "collapse everything" wrapper), so this is
    one level *below* that, not the sidebar root itself any more.

    ``search_panel`` is passed in already built, rather than imported and
    called here directly: the deferred `from .search import search_panel`
    inside `layer_panel()` exists to break a circular import (search.py
    imports `_section`/`_info_icon` back from this module), and that
    import is scoped to `layer_panel()`'s own function body — a second,
    identically-named top-level import here would shadow the *component*
    name `search_panel` with the *function* the moment this module is
    imported, which is exactly the ordering problem the deferred import
    was written to avoid in the first place.
    """
    return rx.accordion.root(
        _group("study_area", "target", AppState.tr["group_study_area"],
              search_panel, point_control(), geometry_control()),
        _group("landcover_base", "layers",
              AppState.tr["group_landcover_base"],
              basemap_control(), mapbiomas_control(), compare_control(),
              change_mask_control()),
        # The user's own framing for this one: IFN, IBAMA and a pasted
        # coordinate list are three different sources for the same
        # thing — a set of ground points/records to check against the
        # map — where the other four groups are each one continuous
        # raster or reference layer.
        _group("ifn_ibama_data", "shield-alert",
              AppState.tr["group_ifn_ibama_data"],
              ifn_control(), multi_select_control(), embargos_control(),
              auto_infracao_control(), user_points_control()),
        _group("ibge_reference", "landmark",
              AppState.tr["group_ibge_reference"],
              biome_control(), ibge_vegetation_control()),
        _group("biomass_forest", "trees",
              AppState.tr["group_biomass_forest"],
              biomass_control(), hansen_control()),
        type="multiple",
        collapsible=True,
        variant="surface",
        width="100%",
        # Every group starts CLOSED — with five multi-control groups, "open
        # by default" meant the sidebar was just as tall as the old flat
        # list until collapsed by hand, so clicking the map still meant
        # scrolling past everything to see what that click produced. Closed
        # by default means the sidebar is short from the start; open only
        # whichever group is actually wanted (no `default_value` at all — a
        # `type="multiple"` accordion with none given simply starts with
        # nothing expanded).
    )
