"""Sidebar controls for the USA map layers."""

from __future__ import annotations

import reflex as rx

from ...config.settings import BUFFER_PREVIEW_RADIUS_KM
from ..config import glc
from ..config import datasets as ds
from ..config import forest as fc_cfg
from ..state import WorldState as S
from ..translations import get_translations


def _tr_year(key: str, year: int) -> rx.Var:
    """A translated string with ``{year}`` filled in at build time.

    ``S.tr[key]`` is a runtime Var and ``.format()`` cannot run on it in the
    component tree — it would render the literal ``{year}``. This year is a
    module constant, so both language variants are formatted once here and
    switched with ``rx.cond``. (Where the year is *dynamic*, the formatting has
    to be a computed var instead — see ``state/_analysis.top_classes_title``.)
    """
    return rx.cond(
        S.language == "pt",
        get_translations("pt")[key].format(year=year),
        get_translations("en")[key].format(year=year),
    )


def _info_icon(text: rx.Var | str) -> rx.Component:
    """A tap/click affordance, not a hover tooltip — ported from the Brazil
    page's ``components/layer_panel.py::_info_icon`` unchanged: this app is
    mobile-first throughout, and hover has no equivalent on touch."""
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


def _section(title, *children, info: rx.Var | str | None = None) -> rx.Component:
    """``info`` added for gbif_control() — the first Canada-page section that
    needs the same tap-to-read explainer the Brazil sidebar already has on
    several of its own sections."""
    header = rx.text(title, size="1", weight="bold", color_scheme="gray",
                     style={"textTransform": "uppercase", "letterSpacing": "0.06em"})
    return rx.vstack(
        rx.hstack(header, _info_icon(info), spacing="1", align="center")
        if info is not None else header,
        *children,
        spacing="2", align_items="stretch", width="100%",
    )


def _filter_select(label: str, options, value, on_change,
                   disabled=False) -> rx.Component:
    """One row of the GBIF filter accordion — ported from the Brazil page's
    ``components/layer_panel.py::_filter_select`` unchanged."""
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


def _slider_row(label, value_text) -> rx.Component:
    return rx.hstack(
        rx.text(label, size="1", color_scheme="gray"),
        rx.spacer(),
        rx.text(value_text, size="1"),
        width="100%",
    )


def point_control() -> rx.Component:
    return _section(
        S.tr["section_point"],
        rx.cond(
            S.has_point,
            rx.vstack(
                rx.hstack(
                    rx.icon("map-pin", size=14, color="var(--jade-11)"),
                    rx.text(S.point_label, size="2", weight="medium"),
                    spacing="2", align="center",
                ),
                rx.text(S.tr["point_click_other"], size="1", color_scheme="gray"),
                spacing="1", align_items="start", width="100%",
            ),
            rx.cond(
                S.point_error != "",
                rx.callout(S.point_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.text(S.tr["point_click_choose"], size="1", color_scheme="gray"),
            ),
        ),
    )


def basemap_control() -> rx.Component:
    return _section(
        S.tr["section_basemap"],
        rx.select(
            S.basemap_options,
            value=S.basemap_label,
            on_change=S.set_basemap_by_label,
            width="100%",
        ),
    )


def landsat_control() -> rx.Component:
    return _section(
        S.tr["section_landsat"],
        rx.hstack(
            rx.switch(checked=S.show_landsat, on_change=S.toggle_landsat),
            rx.text(S.landsat_value, size="2"),
            rx.spacer(),
            rx.cond(S.layer_busy, rx.spinner(size="1"), rx.fragment()),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            S.show_landsat,
            rx.vstack(
                rx.select(
                    S.landsat_options,
                    value=S.landsat_value,
                    on_change=S.set_landsat_rendering,
                    width="100%", size="2",
                ),
                _slider_row(S.tr["landsat_year_label"],
                            S.landsat_year.to_string()),
                rx.slider(
                    min=ds.LANDSAT_YEAR_START, max=ds.LANDSAT_YEAR_END, step=1,
                    default_value=[2024], on_change=S.set_landsat_year,
                    width="100%",
                ),
                rx.text(S.landsat_note, size="1", color_scheme="gray"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
    )


def glc_control() -> rx.Component:
    return _section(
        S.tr["section_landcover"],
        rx.hstack(
            rx.switch(checked=S.show_glc, on_change=S.toggle_glc),
            rx.text(S.tr["glc_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            S.show_glc,
            rx.vstack(
                rx.hstack(
                    rx.text(S.tr["year_label"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(S.glc_year.to_string(), color_scheme="green",
                             variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=glc.GLC_YEAR_START, max=glc.GLC_YEAR_END, step=1,
                    default_value=[glc.GLC_YEAR_END],
                    on_change=S.set_glc_year, width="100%",
                ),
                rx.hstack(
                    rx.text(str(glc.GLC_YEAR_START), size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.text(str(glc.GLC_YEAR_END), size="1", color_scheme="gray"),
                    width="100%",
                ),
                _slider_row(S.tr["opacity_label"],
                            S.glc_opacity_pct.to_string() + "%"),
                rx.slider(min=0, max=100, step=5, default_value=[75],
                          on_change=S.set_glc_opacity, width="100%"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        rx.hstack(rx.switch(checked=S.compare_on, on_change=S.toggle_compare),
                  rx.text(S.tr["compare_toggle"], size="2"), width="100%", align="center", spacing="2"),
        rx.cond(S.compare_on, rx.vstack(
            rx.hstack(rx.text(S.tr["compare_year_left"], size="1", color_scheme="gray"), rx.spacer(),
                      rx.badge(S.compare_year.to_string(), color_scheme="amber", variant="solid"), width="100%"),
            rx.slider(min=glc.GLC_YEAR_START, max=glc.GLC_YEAR_END, step=1,
                      default_value=[glc.GLC_YEAR_START], on_change=S.set_compare_year, width="100%"),
            rx.text(S.tr["compare_note"], size="1", color_scheme="gray"),
            spacing="2", width="100%", padding_top="0.25rem"), rx.fragment()),
        rx.cond(S.east_missing,
                rx.button(S.tr["east_toggle"], on_click=S.load_east, variant="soft", size="1"),
                rx.fragment()),
        rx.text(S.tr["glc_coverage_note"], size="1", color_scheme="gray"),
    )


def buffer_preview_control() -> rx.Component:
    """The magnifier: land cover shown only inside the analysis radius."""
    return _section(
        S.tr["section_buffer_preview"],
        rx.hstack(
            rx.switch(checked=S.show_buffer_preview,
                      on_change=S.toggle_buffer_preview),
            rx.text(S.tr["buffer_preview_toggle_label"], size="2"),
            rx.spacer(),
            rx.badge(f"{BUFFER_PREVIEW_RADIUS_KM:g} km", size="1",
                     variant="soft", color_scheme="gray"),
            width="100%", align="center", spacing="2",
        ),
        rx.text(_tr_year("buffer_preview_text", glc.GLC_YEAR_END),
                size="1", color_scheme="gray"),
        rx.cond(
            S.show_glc,
            rx.text(S.tr["buffer_preview_hidden_note"], size="1",
                    color_scheme="amber"),
            rx.fragment(),
        ),
    )


def disturbance_layers_control() -> rx.Component:
    """The year of the most recent tree-cover loss (Hansen) and of the most recent burn (MODIS)."""
    from ..config import disturbance as dcfg
    return _section(
        S.tr["section_disturbance_layers"],
        rx.hstack(rx.switch(checked=S.show_loss_year, on_change=S.toggle_loss_year),
                  rx.text(S.tr["loss_year_toggle"], size="2"), width="100%", align="center", spacing="2"),
        rx.cond(S.show_loss_year, rx.text(S.tr["loss_year_note"], size="1", color_scheme="gray"), rx.fragment()),
        rx.hstack(rx.switch(checked=S.show_burn_year, on_change=S.toggle_burn_year),
                  rx.text(S.tr["burn_year_toggle"], size="2"), width="100%", align="center", spacing="2"),
        rx.cond(S.show_burn_year, rx.text(S.tr["burn_year_note"], size="1", color_scheme="gray"), rx.fragment()),
    )


def forest_change_control() -> rx.Component:
    return _section(
        S.tr["section_forest_change"],
        rx.hstack(
            rx.switch(checked=S.show_treecover, on_change=S.toggle_treecover),
            rx.text(S.tr["hansen_treecover_toggle"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            S.show_treecover,
            rx.vstack(
                _slider_row(S.tr["opacity_label"],
                            S.treecover_opacity_pct.to_string() + "%"),
                rx.slider(min=0, max=100, step=5, default_value=[60],
                          on_change=S.set_treecover_opacity, width="100%"),
                spacing="1", width="100%",
            ),
            rx.fragment(),
        ),
        rx.hstack(
            rx.switch(checked=S.show_change, on_change=S.toggle_change),
            rx.text(S.tr["forest_change_toggle_label"], size="2"),
            width="100%", align="center", spacing="2",
        ),
        rx.cond(
            S.show_change,
            rx.vstack(
                rx.hstack(
                    rx.text(S.tr["change_base_year"], size="1", color_scheme="gray"),
                    rx.spacer(),
                    rx.badge(S.change_from_year.to_string(), color_scheme="red",
                             variant="solid"),
                    width="100%",
                ),
                rx.slider(
                    min=fc_cfg.HANSEN_LOSS_YEAR_START,
                    max=fc_cfg.HANSEN_LOSS_YEAR_END, step=1,
                    default_value=[fc_cfg.HANSEN_LOSS_YEAR_START],
                    on_change=S.set_change_from_year, width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=fc_cfg.HANSEN_LOSS_COLOR),
                    rx.text(S.tr["change_loss_label"], size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.box(width="10px", height="10px", border_radius="2px",
                           background=fc_cfg.HANSEN_GAIN_COLOR),
                    rx.text(S.tr["change_gain_label"], size="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.text(S.tr["forest_change_note"], size="1", color_scheme="gray"),
                spacing="2", width="100%", padding_top="0.25rem",
            ),
            rx.fragment(),
        ),
        # Governs both Hansen layers and the change numbers, so it sits outside
        # either toggle rather than being buried under one of them.
        _slider_row(S.tr["treecover_threshold_label"],
                    S.treecover_threshold.to_string() + "%"),
        rx.slider(min=0, max=90, step=5, default_value=[30],
                  on_change=S.set_treecover_threshold, width="100%"),
    )


def status_line() -> rx.Component:
    return rx.hstack(
        rx.cond(
            S.ee_error != "",
            rx.icon("triangle-alert", size=14, color="var(--red-9)"),
            rx.cond(S.ee_ready,
                    rx.icon("circle-check", size=14, color="var(--green-9)"),
                    rx.spinner(size="1")),
        ),
        rx.text(S.ee_status_label, size="1", color_scheme="gray"),
        spacing="2", align="center", width="100%",
    )


def layer_panel(fill_height: bool = True) -> rx.Component:
    """The Brazil page's arrangement: search on top, then topic groups in one collapsible
    wrapper (``components/panel_kit.py``). ``fill_height=False`` is for the mobile sheet."""
    # Imported here, not at module level: gbif_panel.py imports _section/_info_icon/_filter_select
    # back from this module.
    from ...components.panel_kit import group_item, grouped_panel
    from .gbif_panel import gbif_control
    from .search import search_panel

    return grouped_panel(
        S, search=search_panel(), fill_height=fill_height, status=status_line(),
        groups=[
            group_item("study_area", "target", S.tr["group_study_area"], point_control()),
            group_item("landcover", "layers", S.tr["group_landcover"],
                       basemap_control(), landsat_control(), glc_control(), buffer_preview_control()),
            group_item("forest", "trees", S.tr["group_forest"],
                       disturbance_layers_control(), forest_change_control()),
            group_item("biodiversity", "bug", S.tr["group_biodiversity"], gbif_control()),
        ])
