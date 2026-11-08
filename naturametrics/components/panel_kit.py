"""The Brazil page's grouped sidebar and mobile bottom sheet, for the Canada and USA pages.

The Brazil page (``components/layer_panel.py``, ``pages/index.py``) groups its controls into a
few collapsible topic groups and, below desktop, puts the controls and the results in one
draggable bottom sheet instead of an overlay drawer. This module is the same thing for the two
pages that were forked from the Canada page, taking the page's own state ``S`` so it needs no
copy of the Brazil state:

* :func:`group_item` — one collapsible group (a bordered card), the Brazil ``_group``;
* :func:`grouped_panel` — search box on top, one outer "layers and analysis" accordion holding the
  groups (controlled by ``S.open_groups`` / ``S.set_open_groups``), status line and engine error;
* :func:`mobile_sheet` — the draggable sheet (peek / half / full) and its script, the Brazil
  ``_mobile_sheet`` / ``_SHEET_SCRIPT`` reused as they are (same element ids, same script).

Page state must provide: ``tr`` (with ``drawer_title``, ``sheet_handle_aria``), ``open_groups``,
``set_open_groups`` and ``ee_error``.
"""

from __future__ import annotations

import reflex as rx

from .layer_panel import _group
from .tab_style import TAB_CHIP, TAB_LIST
from ..pages.index import _SHEET_SCRIPT, _drag_handle  # noqa: F401  (script is run by the page)

MOBILE_ONLY = ["flex", "flex", "flex", "none"]
DESKTOP_ONLY = ["none", "none", "none", "flex"]

#: Same font-size shrink as the Brazil panel: every control uses size 1/2 text.
_PANEL_STYLE = {
    "--font-size-1": "calc(var(--font-size-1) - 3px)",
    "--font-size-2": "calc(var(--font-size-2) - 3px)",
}


def group_item(value: str, icon: str, title, *sections: rx.Component) -> rx.Component:
    return _group(value, icon, title, *sections)


def grouped_panel(S, *, search: rx.Component, groups: list[rx.Component], status: rx.Component,
                  fill_height: bool = True) -> rx.Component:
    """Search on top, the groups inside one collapsible wrapper, then the status line.

    ``fill_height=False`` is what the mobile sheet needs: the panel then shares a scrolling box
    with the results (see ``components/layer_panel.py::layer_panel`` for the overlap bug that
    ``height="100%"`` caused there).
    """
    return rx.vstack(
        search,
        rx.accordion.root(
            rx.accordion.item(
                rx.accordion.header(rx.accordion.trigger(rx.hstack(
                    rx.icon("panel-left", size=15),
                    rx.text(S.tr["drawer_title"], size="2", weight="bold"),
                    spacing="2", align="center"))),
                rx.accordion.content(
                    rx.accordion.root(
                        *groups,
                        type="multiple", collapsible=True, variant="surface", width="100%",
                        value=S.open_groups, on_value_change=S.set_open_groups,
                    ),
                    padding_x="0",
                ),
                value="all_layers",
            ),
            type="single", collapsible=True, variant="ghost", width="100%",
            default_value="all_layers",
        ),
        rx.spacer(),
        rx.divider(),
        status,
        rx.cond(S.ee_error != "",
                rx.callout(S.ee_error, icon="triangle-alert", color_scheme="red", size="1", width="100%"),
                rx.fragment()),
        spacing="4", align_items="stretch", width="100%", padding="1rem",
        height="100%" if fill_height else "auto",
        style=_PANEL_STYLE,
    )


def mobile_sheet(S, panel: rx.Component, results: rx.Component, accent: str) -> rx.Component:
    """Below desktop: one draggable bottom sheet holding the controls and the results."""
    handle = rx.box(
        rx.box(
            rx.icon("chevron-up", size=16, color="white", custom_attrs={"data-chevron": "1"},
                    style={"transition": "transform 200ms ease"}),
            custom_attrs={"data-sheet-tab": "1"},
            display="flex", align_items="center", justify_content="center",
            width="56px", height="22px", background=f"var(--{accent}-9)", border_radius="11px",
            box_shadow="0 2px 6px rgba(0, 0, 0, 0.3)"),
        id="nm-mobile-sheet-handle",
        custom_attrs={"data-drawer-handle": "nm-mobile-sheet"},
        tab_index=0, role="slider", aria_label=S.tr["sheet_handle_aria"], outline="none",
        display="flex", justify_content="center", align_items="center",
        width="100%", height="30px", cursor="ns-resize", flex_shrink="0", padding_top="4px",
        _focus_visible={"background": "var(--gray-4)", "box_shadow": "inset 0 0 0 2px var(--accent-8)"},
    )
    return rx.vstack(
        handle,
        rx.box(panel, results, overflow_y="auto", flex="1", min_height="0"),
        id="nm-mobile-sheet", display=MOBILE_ONLY, flex_direction="column",
        align="stretch",                      # not "start": see pages/index.py::_mobile_sheet
        position="fixed", bottom="0", left="0", right="0", height="45vh", max_height="45vh",
        background="var(--color-panel-solid)",
        border_top_left_radius="var(--radius-4)", border_top_right_radius="var(--radius-4)",
        box_shadow="0 -4px 24px rgba(0, 0, 0, 0.25)", z_index="1000", overflow="hidden", spacing="0",
    )


def workspace_with_sheet(S, *, map_pane: rx.Component, results, panel_for_sheet, accent: str) -> rx.Component:
    """One map, one flex column at every breakpoint; the sheet floats over it below desktop and
    the results sit under the map on desktop (the Brazil page's ``workspace_main``).

    ``results`` and ``panel_for_sheet`` are **callables**: each is rendered twice (desktop and
    sheet), and a component instance must not appear twice in one tree."""
    return rx.vstack(
        rx.box(map_pane, width="100%", flex="1 1 auto", min_height="0", position="relative"),
        rx.box(results(), display=DESKTOP_ONLY),
        mobile_sheet(S, panel_for_sheet(), results(), accent),
        width="100%", height="100%", spacing="0", align_items="stretch",
        on_mount=rx.call_script(_SHEET_SCRIPT),
    )


# --------------------------------------------------------------------------- #
# Results area: the Brazil page's right-hand tabs, on the Canada and USA pages
# --------------------------------------------------------------------------- #
def right_tabs(items: list[tuple[str, rx.Var, rx.Component]]) -> rx.Component:
    """Tabs in the results area's right column, the Brazil page's arrangement: one trigger per
    analysis, the first one open. ``items`` = (value, label, content)."""
    # The right padding keeps the last chip clear of the Resize button above the panel.
    return rx.tabs.root(
        rx.tabs.list(
            *[rx.tabs.trigger(label, value=value, title=label, style=TAB_CHIP) for value, label, _ in items],
            style={**TAB_LIST, "paddingRight": "4.8rem"},
            width="100%",
        ),
        *[rx.tabs.content(content, value=value, padding_top="0.6rem", width="100%")
          for value, _, content in items],
        default_value=items[0][0], width="100%",
    )


def data_table(headers: list, rows, keys: list[str]) -> rx.Component:
    """A compact table over a list of dicts (values already formatted as text)."""
    return rx.table.root(
        rx.table.header(rx.table.row(*[rx.table.column_header_cell(h, font_size="1") for h in headers])),
        rx.table.body(rx.foreach(rows, lambda r: rx.table.row(
            *[rx.table.cell(r[k], font_size="1") for k in keys]))),
        size="1", variant="surface", width="100%",
    )


def _state_panel(S, title, hint, running, error, has, body, none_key: str, note_key: str | None) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="2", weight="bold"),
        rx.text(hint, size="1", color_scheme="gray"),
        rx.cond(running, rx.hstack(rx.spinner(size="1"), rx.text(S.tr["extras_running"], size="1")),
                rx.fragment()),
        rx.cond(error != "", rx.callout(error, icon="triangle-alert", color_scheme="amber", size="1",
                                        width="100%"), rx.fragment()),
        rx.cond(has, body,
                rx.cond(~running & (error == ""), rx.text(S.tr[none_key], size="1", color_scheme="gray"),
                        rx.fragment())),
        *([rx.text(S.tr[note_key], size="1", color_scheme="gray")] if note_key else []),
        spacing="2", width="100%", align_items="stretch")


def metrics_panel(S) -> rx.Component:
    """Landscape metrics per radius: patches, largest patch, edge, effective mesh, diversity."""
    return _state_panel(
        S, S.tr["metrics_title"], S.tr["metrics_hint"], S.metrics_running, S.metrics_error,
        S.metrics_has,
        data_table(
            [S.tr["col_radius"], S.tr["col_patches"], S.tr["col_largest"], S.tr["col_edge"],
             S.tr["col_meff"], S.tr["col_shannon"], S.tr["col_evenness"]],
            S.metrics_rows,
            ["radius", "patches", "largest", "edge", "meff", "shannon", "evenness"]),
        "metrics_none", "metrics_attr")


def biomass_panel(S) -> rx.Component:
    """Above-ground biomass by year for the selected radius (ESA CCI, Mg/ha)."""
    return _state_panel(
        S, S.tr["biomass_title"], S.tr["biomass_hint"], S.biomass_running, S.biomass_error,
        S.biomass_has,
        rx.vstack(
            rx.plotly(data=S.biomass_chart_figure, width="100%",
                      config={"displayModeBar": False, "responsive": True}),
            data_table([S.tr["col_year"], S.tr["col_mgha"], S.tr["col_sd"]], S.biomass_rows,
                       ["year", "mean", "sd"]),
            spacing="2", width="100%", align_items="stretch"),
        "biomass_none", "biomass_attr")
