"""The on-map layer control — a floating box in the map's top-right corner,
mirroring camposcope's ``components/map_legend.py``.

One structural difference from camposcope: that app has exactly ONE map
layer at a time, driven by whichever results tab is active, so its legend is
a single ``rx.match`` over the active tab. Naturametrics has no such
single-layer concept — several of its layers (MapBiomas, the change mask,
Hansen tree cover, Hansen loss/gain, IBGE Vegetação, biomass, biomes, IFN
points) can all be on at once, picked independently from the sidebar. So
this legend renders one section per ACTIVE layer instead of one section per
tab, each carrying its own on/off switch — flipping any of them off/on here
is the same state write the sidebar's own switch makes, just reachable
without opening the mobile sheet.
"""

from __future__ import annotations

import reflex as rx

from ..config import datasets as ds
from ..services import change_mask as cm
from ..services.biomass import AGB_YEARS
from ..state import AppState

_BOX_STYLE = dict(
    position="absolute",
    top="12px",
    right="12px",
    background="var(--color-panel-solid)",
    border="1px solid var(--gray-5)",
    border_radius="var(--radius-3)",
    box_shadow="0 2px 8px rgba(0,0,0,.15)",
    padding="8px 10px",
    z_index="900",
    min_width="180px",
    max_width="220px",
    max_height="70vh",
    overflow_y="auto",
    font_size="0.75rem",
)


def _row_header(label, checked, on_change) -> rx.Component:
    return rx.hstack(
        rx.text(label, size="1", weight="medium"),
        rx.spacer(),
        rx.switch(checked=checked, on_change=on_change, size="1"),
        width="100%", align="center",
    )


def _swatch_row(color: str, label) -> rx.Component:
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px",
              background=color, flex_shrink="0"),
        rx.text(label, size="1"),
        spacing="2", align="center",
    )


def _mapbiomas_section() -> rx.Component:
    """Real class swatches when a study point/buffer is selected
    (``summary_rows`` — top 6 classes for the active radius and year);
    otherwise just the year, since the full-country layer has no single
    "active" set of classes to list."""
    return rx.cond(
        AppState.show_mapbiomas,
        rx.vstack(
            _row_header(AppState.tr["section_landcover"],
                       AppState.show_mapbiomas, AppState.toggle_mapbiomas),
            rx.cond(
                AppState.summary_rows,
                rx.vstack(
                    rx.foreach(
                        AppState.summary_rows,
                        lambda r: rx.hstack(
                            rx.box(width="10px", height="10px",
                                  border_radius="2px", background=r["color"],
                                  flex_shrink="0"),
                            rx.text(r["name"], size="1", style={"flex": "1"},
                                   no_of_lines=1),
                            rx.text(r["pct"], size="1",
                                   color="var(--gray-11)"),
                            spacing="2", align="center", width="100%",
                        ),
                    ),
                    spacing="1", width="100%",
                ),
                rx.text(AppState.mapbiomas_year.to_string(), size="1",
                       color="var(--gray-11)"),
            ),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _compare_section() -> rx.Component:
    """No swatch of its own — the pairing already reuses whichever layer's
    classes/colours are shown above (MapBiomas years, IBGE Vegetação, SPOT
    2008). Turning it off here resets the select to "None" directly, the
    same effect the sidebar's own dropdown gives."""
    return rx.cond(
        AppState.compare_mode != "off",
        rx.vstack(
            rx.hstack(
                rx.text(AppState.tr["section_compare"], size="1",
                       weight="medium"),
                rx.spacer(),
                rx.icon_button(
                    rx.icon("x", size=12), size="1", variant="ghost",
                    on_click=AppState.set_compare_mode("off"),
                ),
                width="100%", align="center",
            ),
            rx.text(AppState.compare_mode_label, size="1",
                   color="var(--gray-11)"),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _change_mask_section() -> rx.Component:
    return rx.cond(
        AppState.show_change_mask,
        rx.vstack(
            _row_header(AppState.tr["section_change_mask"],
                       AppState.show_change_mask,
                       AppState.toggle_change_mask),
            _swatch_row(cm.CHANGE_COLORS[cm.CHANGE_LOSS],
                       AppState.tr["change_loss_label"]),
            _swatch_row(cm.CHANGE_COLORS[cm.CHANGE_GAIN],
                       AppState.tr["change_gain_label"]),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _hansen_section() -> rx.Component:
    return rx.cond(
        AppState.show_hansen_treecover | AppState.show_hansen_change,
        rx.vstack(
            rx.text(AppState.tr["section_forest_change"], size="1",
                   weight="medium"),
            rx.cond(
                AppState.show_hansen_treecover,
                rx.hstack(
                    rx.text(AppState.tr["hansen_treecover_toggle"], size="1"),
                    rx.spacer(),
                    rx.switch(checked=AppState.show_hansen_treecover,
                             on_change=AppState.toggle_hansen_treecover,
                             size="1"),
                    width="100%", align="center",
                ),
                rx.fragment(),
            ),
            rx.cond(
                AppState.show_hansen_change,
                rx.vstack(
                    rx.hstack(
                        rx.text(AppState.tr["hansen_change_toggle"], size="1"),
                        rx.spacer(),
                        rx.switch(checked=AppState.show_hansen_change,
                                 on_change=AppState.toggle_hansen_change,
                                 size="1"),
                        width="100%", align="center",
                    ),
                    _swatch_row(ds.HANSEN_GFC["loss_color"],
                               AppState.tr["hansen_loss_label"]),
                    _swatch_row(ds.HANSEN_GFC["gain_color"],
                               AppState.tr["hansen_gain_label"]),
                    spacing="1", width="100%",
                ),
                rx.fragment(),
            ),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _biomass_section() -> rx.Component:
    return rx.cond(
        AppState.show_biomass,
        rx.vstack(
            _row_header(AppState.tr["section_biomass"], AppState.show_biomass,
                       AppState.toggle_biomass),
            rx.hstack(
                rx.box(width="60px", height="8px", border_radius="2px",
                      background="linear-gradient(to right, white, #1a7f37)"),
                spacing="2", align="center",
            ),
            rx.hstack(
                rx.text("0", size="1", color="var(--gray-11)"),
                rx.spacer(),
                rx.text(f"{AGB_YEARS[-1]}", size="1", color="var(--gray-11)"),
                width="100%",
            ),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _ibge_veg_section() -> rx.Component:
    return rx.cond(
        AppState.show_ibge_veg,
        _row_header(AppState.tr["section_ibge_veg"], AppState.show_ibge_veg,
                   AppState.toggle_ibge_veg),
        rx.fragment(),
    )


def _biomes_section() -> rx.Component:
    conf = ds.IBGE_BIOME_DOMAIN
    return rx.cond(
        AppState.show_biomes,
        rx.vstack(
            _row_header(AppState.tr["section_biomes"], AppState.show_biomes,
                       AppState.toggle_biomes),
            *[
                _swatch_row(f"#{conf['palette'][name]}", name)
                for name in conf["biomes"]
            ],
            spacing="1", width="100%",
        ),
        rx.fragment(),
    )


def _ifn_section() -> rx.Component:
    return rx.cond(
        AppState.show_ifn,
        _row_header(AppState.tr["section_ifn"], AppState.show_ifn,
                   AppState.toggle_ifn),
        rx.fragment(),
    )


def map_legend() -> rx.Component:
    """Shown only once at least one analysis layer is on — an empty box
    would just be clutter over the map when the sidebar/sheet has nothing
    active."""
    return rx.cond(
        AppState.any_analysis_layer_active,
        rx.box(
            rx.vstack(
                _mapbiomas_section(),
                _compare_section(),
                _change_mask_section(),
                _hansen_section(),
                _biomass_section(),
                _ibge_veg_section(),
                _biomes_section(),
                _ifn_section(),
                spacing="3", width="100%",
            ),
            **_BOX_STYLE,
        ),
    )
