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


def _section(title: str, *children) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="1", weight="bold", color_scheme="gray",
                style={"textTransform": "uppercase", "letterSpacing": "0.06em"}),
        *children,
        spacing="2",
        align_items="stretch",
        width="100%",
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
                            AppState.compare_enabled,
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
    )


def buffer_preview_control() -> rx.Component:
    """MapBiomas shown only inside the buffer of the point under the cursor."""
    return _section(
        AppState.tr["section_buffer_preview"],
        rx.hstack(
            rx.switch(checked=AppState.show_buffer_preview,
                      on_change=AppState.toggle_buffer_preview),
            rx.text(AppState.tr["buffer_preview_toggle_label"], size="2"),
            rx.spacer(),
            rx.badge(f"{st.BUFFER_PREVIEW_RADIUS_KM:g} km", size="1",
                     variant="soft", color_scheme="gray"),
            width="100%", align="center", spacing="2",
        ),
        rx.text(
            AppState.tr["buffer_preview_text"],
            size="1", color_scheme="gray",
        ),
        rx.cond(
            AppState.show_mapbiomas,
            rx.text(
                AppState.tr["buffer_preview_hidden_note"],
                size="1", color_scheme="amber",
            ),
            rx.fragment(),
        ),
    )


def compare_control() -> rx.Component:
    """Two MapBiomas years at once, split by a draggable vertical divider."""
    return _section(
        AppState.tr["section_compare"],
        rx.hstack(
            rx.switch(checked=AppState.compare_enabled,
                      on_change=AppState.toggle_compare),
            rx.text(AppState.tr["compare_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            AppState.compare_enabled,
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
                    default_value=[35],
                    on_change=AppState.set_biome_opacity,
                    width="100%",
                ),
                _biome_legend(),
                rx.text(
                    AppState.tr["biomes_hover_note"],
                    size="1", color_scheme="gray",
                ),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
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
            spacing="1", align_items="start", width="100%",
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
        ifn_control(),
        multi_select_control(),
        rx.divider(),
        user_points_control(),
        rx.divider(),
        biome_control(),
        rx.divider(),
        biomass_control(),
        rx.divider(),
        ibge_vegetation_control(),
        rx.divider(),
        hansen_control(),
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
