"""The on-map layer control — a floating box in the map's top-right corner,
mirroring the Brazil page's own ``components/map_legend.py``. Same shape:
several layers (ACI, forest age, Hansen tree cover, Hansen loss/gain,
Landsat) can be on at once here too, so this is one section per ACTIVE
layer rather than a single tab-driven legend.
"""

from __future__ import annotations

import reflex as rx

from ..config import forest as fc_cfg
from ..state import CanadaState as S

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


def _aci_section() -> rx.Component:
    """Real class swatches when a study point is selected (``summary_rows``
    — top 6 classes for the selected radius, latest year); otherwise just
    the year, since the full-province layer has no single "active" set of
    classes to list."""
    return rx.cond(
        S.show_aci,
        rx.vstack(
            _row_header(S.tr["section_landcover"], S.show_aci, S.toggle_aci),
            rx.cond(
                S.summary_rows,
                rx.vstack(
                    rx.foreach(
                        S.summary_rows,
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
                rx.text(S.aci_year.to_string(), size="1",
                       color="var(--gray-11)"),
            ),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _forest_age_section() -> rx.Component:
    return rx.cond(
        S.show_forest_age,
        _row_header(S.tr["section_forest_age"], S.show_forest_age,
                   S.toggle_forest_age),
        rx.fragment(),
    )


def _hansen_section() -> rx.Component:
    return rx.cond(
        S.show_treecover | S.show_change,
        rx.vstack(
            rx.text(S.tr["section_forest_change"], size="1", weight="medium"),
            rx.cond(
                S.show_treecover,
                rx.hstack(
                    rx.text(S.tr["hansen_treecover_toggle"], size="1"),
                    rx.spacer(),
                    rx.switch(checked=S.show_treecover,
                             on_change=S.toggle_treecover, size="1"),
                    width="100%", align="center",
                ),
                rx.fragment(),
            ),
            rx.cond(
                S.show_change,
                rx.vstack(
                    rx.hstack(
                        rx.text(S.tr["forest_change_toggle_label"], size="1"),
                        rx.spacer(),
                        rx.switch(checked=S.show_change,
                                 on_change=S.toggle_change, size="1"),
                        width="100%", align="center",
                    ),
                    _swatch_row(fc_cfg.HANSEN_LOSS_COLOR,
                               S.tr["change_loss_label"]),
                    _swatch_row(fc_cfg.HANSEN_GAIN_COLOR,
                               S.tr["change_gain_label"]),
                    spacing="1", width="100%",
                ),
                rx.fragment(),
            ),
            spacing="2", width="100%",
        ),
        rx.fragment(),
    )


def _landsat_section() -> rx.Component:
    return rx.cond(
        S.show_landsat,
        _row_header(S.tr["section_landsat"], S.show_landsat, S.toggle_landsat),
        rx.fragment(),
    )


def map_legend() -> rx.Component:
    """Shown only once at least one analysis layer is on — an empty box
    would just be clutter over the map when the sidebar has nothing
    active."""
    return rx.cond(
        S.show_aci | S.show_forest_age | S.show_treecover | S.show_change
        | S.show_landsat,
        rx.box(
            rx.vstack(
                _aci_section(),
                _forest_age_section(),
                _hansen_section(),
                _landsat_section(),
                spacing="3", width="100%",
            ),
            **_BOX_STYLE,
        ),
    )
