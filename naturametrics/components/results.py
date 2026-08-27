"""Results drawer: land-cover history and forest age, side by side.

The two halves are deliberately separate components (doc/10-forest-age.md): they
answer different questions from related but distinct MapBiomas products, and
keeping their own header/body/provenance line each means one failing (e.g. the DSV
asset above having a hiccup) never blanks the other.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState

#: Standard chart config across the app: no Plotly modebar (see the history-
#: chart's own comment below — the modebar has no "away" state on touch, where
#: it would sit permanently on top of the plot). Export instead goes through
#: _chart_export_button, a plain icon placed outside the plot's own hit area.
_PLOTLY_CONFIG = {"displayModeBar": False, "displaylogo": False, "responsive": True}


def _chart_export_button(wrap_id: str, filename: str) -> rx.Component:
    """A small "download this chart" icon, deliberately not Plotly's own
    modebar button (see _PLOTLY_CONFIG above for why that one stays off).
    Plotly.downloadImage runs entirely client-side — no server round-trip,
    no kaleido/headless-browser dependency (the browser already drew the
    figure; this just rasterises it).

    Targets the plot via ``.js-plotly-plot`` — the class Plotly.js itself
    always stamps onto the graph div it creates, part of its own public DOM
    contract (its own modebar button finds "self" the same way) — inside a
    plain ``id`` on the wrapping box, rather than a ``divId`` prop threaded
    through react-plotly.js's wrapper: a first attempt using ``div_id`` on
    ``rx.plotly`` threw at click time (that prop was not reaching the actual
    rendered node the way the react-plotly.js docs suggest it should), while
    a bare HTML ``id`` on a plain ``rx.box`` has no such wrapper-specific
    plumbing to go wrong.

    The icon's own ``rx.icon(..., size=...)`` is not set here: IconButton.create
    (reflex/components/radix/themes/components/icon_button.py) unconditionally
    overwrites its child icon's size from the button's own ``size`` token via
    RADIX_TO_LUCIDE_SIZE, so any size passed to the inner icon is silently
    discarded — the button's size="2" below is what actually renders at 24px."""
    return rx.tooltip(
        rx.icon_button(
            rx.icon("image-down"),
            on_click=rx.call_script(
                "(function(){"
                f"var gd = document.querySelector('#{wrap_id} .js-plotly-plot');"
                "if (gd && window.Plotly) { window.Plotly.downloadImage(gd, "
                f"{{format: 'png', filename: '{filename}', scale: 2}}); }}"
                "})()"
            ),
            size="2", variant="ghost", color_scheme="gray",
            aria_label=AppState.tr["export_chart_aria"],
        ),
        content=AppState.tr["export_chart_label"],
    )


def _table_export_button(on_click) -> rx.Component:
    """The table counterpart of _chart_export_button — a plain CSV of the
    same records already on screen, for a paper's own reprocessing rather
    than a screenshot."""
    return rx.tooltip(
        rx.icon_button(
            rx.icon("download"),
            on_click=on_click,
            size="2", variant="ghost", color_scheme="gray",
            aria_label=AppState.tr["export_table_aria"],
        ),
        content=AppState.tr["export_table_label"],
    )


def _chart_box(figure, wrap_id: str, filename: str, height,
               box_props: dict | None = None) -> rx.Component:
    """A plotly chart plus its own export icon — the one shape shared by
    every chart in this file, so the config/wrap id/icon placement cannot
    drift between charts one at a time. ``box_props`` carries whatever the
    surrounding layout needs on the outer box (e.g. the flex/min_width a
    chart shares a row with a side column under) — the plot itself always
    fills it at width="100%".

    The icon sits in its own slim row *below* the plot, not layered on top
    of it: an absolutely-positioned overlay (the first version of this)
    sat on top of the chart's own corner — legend, hover targets, axis —
    rather than in the blank space every chart already has underneath.
    """
    return rx.box(
        rx.plotly(data=figure, config=_PLOTLY_CONFIG, width="100%", height=height),
        rx.hstack(
            rx.spacer(),
            _chart_export_button(wrap_id, filename),
            width="100%", padding_top="0.15rem",
        ),
        id=wrap_id, width="100%",
        **(box_props or {}),
    )


def _legend_row(row: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px",
               background=row["color"], flex_shrink="0"),
        rx.text(row["name"], size="1", flex="1", no_of_lines=1),
        rx.text(row["area"], size="1", color_scheme="gray"),
        rx.text(row["pct"], size="1", weight="medium", width="46px",
                text_align="right"),
        spacing="2", align="center", width="100%",
    )


def _multi_view_toggle() -> rx.Component:
    """"Soma" vs "Área total" — only meaningful once several points are
    selected, so it stays hidden the rest of the time (results.py callers
    gate this behind AppState.multi_active)."""
    return rx.hstack(
        rx.segmented_control.root(
            rx.foreach(
                AppState.multi_view_options,
                lambda opt: rx.segmented_control.item(opt, value=opt),
            ),
            value=AppState.multi_view_value,
            on_change=AppState.set_multi_view_mode,
            size="1",
        ),
        rx.cond(
            AppState.multi_bbox_any_loading,
            rx.spinner(size="1"),
            rx.fragment(),
        ),
        spacing="1", align="center",
    )


def _land_use_panel() -> rx.Component:
    return rx.vstack(
        # --- header ---------------------------------------------- #
        # Wraps instead of overflowing: on a phone the title, the coordinate
        # badge and the radius control cannot share one row.
        rx.flex(
            rx.hstack(
                rx.icon("chart-column", size=15, color="var(--jade-11)"),
                rx.text(AppState.tr["landuse_title"], size="2", weight="bold",
                        white_space="nowrap"),
                # The coordinate is already shown in the side panel, so on a
                # phone it is dropped rather than allowed to collide with the
                # radius control.
                rx.cond(
                    AppState.multi_active,
                    rx.badge(AppState.multi_label, variant="soft", size="1",
                             color_scheme="jade"),
                    rx.cond(
                        AppState.point_label != "",
                        rx.badge(AppState.point_label, variant="soft", size="1",
                                 display=["none", "none", "inline-flex",
                                          "inline-flex"]),
                        rx.fragment(),
                    ),
                ),
                # Second entry point to the same dialog as the header button:
                # this is where the user is looking when they decide they want
                # the numbers behind the chart.
                rx.cond(
                    AppState.has_result | AppState.multi_active,
                    rx.button(
                        rx.icon("download", size=13),
                        rx.text(AppState.tr["download_button"], size="1"),
                        on_click=AppState.set_export_open(True),
                        size="1", variant="ghost", color_scheme="jade",
                        aria_label=AppState.tr["download_point_aria"],
                    ),
                    rx.fragment(),
                ),
                spacing="2", align="center",
                # Full-width line on phone, shares the row from tablet up.
                flex=["1 1 100%", "1 1 100%", "1 1 auto", "1 1 auto"],
                min_width="0",
            ),
            rx.hstack(
                rx.cond(AppState.multi_active, _multi_view_toggle(), rx.fragment()),
                rx.cond(
                    AppState.region_mode_active,
                    rx.badge(AppState.region_mode_label, size="1",
                             variant="soft", color_scheme="gray"),
                    rx.segmented_control.root(
                        rx.foreach(
                            AppState.radius_options,
                            lambda opt: rx.segmented_control.item(opt, value=opt),
                        ),
                        value=AppState.selected_radius_label,
                        on_change=AppState.set_selected_radius,
                        size="1",
                    ),
                ),
                rx.cond(
                    # The "circle radius"/"square side" caption has nothing to
                    # refer to for a drawn/uploaded region's own boundary.
                    ~AppState.geometry_active,
                    rx.text(AppState.buffer_extent_caption, size="1",
                            color_scheme="gray", white_space="nowrap"),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.switch(checked=AppState.normalise_chart,
                              on_change=AppState.toggle_normalise, size="1"),
                    rx.text("%", size="1", color_scheme="gray"),
                    spacing="1", align="center",
                ),
                spacing="2", align="center",
            ),
            width="100%", align="center", justify="between",
            wrap="wrap", gap="0.5rem",
        ),

        # --- body ------------------------------------------------ #
        rx.cond(
            AppState.analysis_running | AppState.multi_bbox_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="2"),
                    rx.text(
                        rx.cond(AppState.multi_bbox_loading,
                               AppState.tr["full_area_running"],
                               AppState.tr["analysis_running"]),
                        size="1", color_scheme="gray",
                    ),
                    spacing="2", align="center",
                ),
                height="300px", width="100%",
            ),
            rx.cond(
                AppState.analysis_error != "",
                rx.callout(AppState.analysis_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.cond(
                    AppState.has_result | AppState.multi_active,
                    rx.flex(
                        _chart_box(
                            AppState.history_figure, "nm-plot-history",
                            "naturametrics_uso_do_solo",
                            ["300px", "320px", "340px", "340px"],
                            box_props={
                                "flex": ["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                                "min_width": "0",
                            },
                        ),
                        rx.vstack(
                            rx.text(
                                AppState.tr["top_classes_title"],
                                size="1", weight="bold", color_scheme="gray",
                                style={"textTransform": "uppercase",
                                       "letterSpacing": "0.06em"},
                            ),
                            rx.foreach(AppState.summary_rows, _legend_row),
                            rx.spacer(),
                            rx.text(AppState.provenance_line, size="1",
                                    color_scheme="gray"),
                            spacing="2",
                            width=["100%", "100%", "100%", "230px"],
                            flex_shrink=["1", "1", "1", "0"],
                            align_items="stretch",
                            height=["auto", "auto", "auto", "340px"],
                        ),
                        width="100%",
                        # Typed literal props need rx.breakpoints(); a plain
                        # list only works for style props.
                        direction=rx.breakpoints(initial="column", lg="row"),
                        gap="1rem", align="start",
                    ),
                    rx.fragment(),
                ),
            ),
        ),
        width="100%", spacing="3", align_items="stretch",
    )


def _age_summary_line(row: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(AppState.tr["area_natural_label"], size="1", color_scheme="gray"),
            rx.spacer(),
            rx.text(row["total"], size="1", weight="medium"),
            width="100%",
        ),
        rx.hstack(
            rx.text(AppState.tr["median_label"], size="1", color_scheme="gray"),
            rx.spacer(),
            rx.text(row["median"], size="1", weight="medium"),
            width="100%",
        ),
        rx.hstack(
            rx.box(width="10px", height="10px", border_radius="2px",
                   background="#264653", flex_shrink="0"),
            rx.text(AppState.tr["no_change_label"], size="1", flex="1"),
            rx.text(row["censored_pct"], size="1", weight="medium"),
            spacing="2", align="center", width="100%",
        ),
        rx.text(row["censored_area"], size="1", color_scheme="gray",
                text_align="right", width="100%"),
        # The leftover room below the four lines above: loss/gain since the
        # Forest Code baseline (2008) for this same buffer, already computed by
        # services.change_mask for the map-layer toggle and now given its first
        # chart rendering rather than only tile pixels.
        rx.cond(
            AppState.change_has_data,
            rx.vstack(
                rx.text(AppState.tr["change_title"], size="1", weight="bold",
                        color_scheme="gray",
                        style={"textTransform": "uppercase",
                               "letterSpacing": "0.06em"}),
                _chart_box(AppState.change_figure, "nm-plot-change",
                          "naturametrics_mudanca_2008_2024", "150px"),
                spacing="1", width="100%", padding_top="0.5rem",
            ),
            rx.fragment(),
        ),
        spacing="1",
        # A fixed side column on desktop, same as the land-use panel's summary
        # (results.py _land_use_panel): a bare width="100%" here has nothing to
        # be 100% *of* except the flex row it shares with the chart, so it fought
        # the chart's flex="1 1 0" for the same space and the chart's box (with
        # its own min_width="0" letting it shrink) rendered underneath these
        # lines instead of beside them.
        width=["100%", "100%", "100%", "200px"],
        flex_shrink=["1", "1", "1", "0"],
        align_items="stretch",
    )


def _landscape_metric_row(row: rx.Var) -> rx.Component:
    return rx.grid(
        rx.text(row["buffer"], size="1", weight="medium"),
        rx.text(row["patches"], size="1"),
        rx.text(row["patch_density"], size="1"),
        rx.text(row["largest"], size="1"),
        rx.text(row["edge"], size="1"),
        rx.text(row["meff"], size="1"),
        rx.text(row["shannon"], size="1"),
        rx.text(row["simpson"], size="1"),
        rx.text(row["evenness"], size="1"),
        columns="repeat(9, minmax(0, 1fr))",
        gap="0.4rem", width="100%",
    )


def _landscape_metrics_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                "NP · PD · LPI · ED · Meff · Shannon · Simpson",
                size="1", color_scheme="gray",
            ),
            rx.spacer(),
            rx.cond(
                AppState.landscape_metrics_has_result,
                _table_export_button(AppState.download_landscape_metrics_csv),
                rx.fragment(),
            ),
            width="100%", align="center",
        ),
        rx.grid(
            *[rx.text(AppState.tr[key], size="1", weight="bold") for key in (
                "metrics_buffer", "metrics_patches", "metrics_patch_density",
                "metrics_lpi", "metrics_edge_density", "metrics_meff",
                "metrics_shannon", "metrics_simpson", "metrics_evenness")],
            columns="repeat(9, minmax(0, 1fr))",
            gap="0.4rem", width="100%",
        ),
        rx.cond(
            AppState.landscape_metrics_busy,
            rx.spinner(size="1"),
            rx.cond(
                # landscape_metrics_error is only ever set by the single-point
                # path (run_analysis) — showing it in multi-select would risk
                # surfacing a stale error left over from an earlier point.
                (AppState.landscape_metrics_error != "") & ~AppState.multi_mode,
                rx.text(AppState.landscape_metrics_error, size="1",
                        color_scheme="amber"),
                rx.cond(
                    AppState.landscape_metrics_has_result,
                    rx.foreach(AppState.landscape_metrics_rows,
                               _landscape_metric_row),
                    rx.text(AppState.tr["landscape_metrics_empty"], size="1",
                            color_scheme="gray"),
                ),
            ),
        ),
        rx.text(AppState.landscape_metrics_provenance_line, size="1",
                color_scheme="gray"),
        _connectivity_section(),
        spacing="2", width="100%", overflow_x="auto",
    )


def _connectivity_row(row: rx.Var) -> rx.Component:
    return rx.grid(
        rx.text(row["buffer"], size="1", weight="medium"),
        rx.text(row["n_fragments"], size="1"),
        rx.text(row["enn_mean"], size="1"),
        rx.text(row["enn_median"], size="1"),
        columns="repeat(4, minmax(0, 1fr))",
        gap="0.4rem", width="100%",
    )


def _connectivity_section() -> rx.Component:
    """The costly, opt-in half of landscape metrics — mean/median distance to
    the nearest forest fragment (services.connectivity), behind its own
    button rather than fetched alongside the table above (see that module's
    docstring for why it is not free the way meff_ha is)."""
    return rx.cond(
        AppState.connectivity_available,
        rx.vstack(
            rx.divider(),
            rx.text(AppState.tr["connectivity_hint"], size="1", color_scheme="gray"),
            rx.button(
                rx.icon("route", size=13),
                rx.text(AppState.tr["connectivity_run_button"], size="1"),
                on_click=AppState.run_connectivity,
                loading=AppState.connectivity_running,
                disabled=AppState.connectivity_running,
                size="1", variant="soft", color_scheme="amber",
            ),
            rx.cond(
                AppState.connectivity_error != "",
                rx.text(AppState.connectivity_error, size="1", color_scheme="amber"),
                rx.cond(
                    AppState.connectivity_has_result,
                    rx.vstack(
                        rx.hstack(
                            rx.grid(
                                *[rx.text(AppState.tr[key], size="1", weight="bold")
                                  for key in ("metrics_buffer", "connectivity_n_fragments",
                                             "connectivity_enn_mean",
                                             "connectivity_enn_median")],
                                columns="repeat(4, minmax(0, 1fr))",
                                gap="0.4rem", flex="1",
                            ),
                            _table_export_button(AppState.download_connectivity_csv),
                            width="100%", align="center",
                        ),
                        rx.foreach(AppState.connectivity_rows, _connectivity_row),
                        rx.text(AppState.connectivity_provenance_line, size="1",
                                color_scheme="gray"),
                        spacing="1", width="100%",
                    ),
                    rx.cond(
                        AppState.connectivity_running,
                        rx.fragment(),
                        rx.text(AppState.tr["connectivity_empty"], size="1",
                                color_scheme="gray"),
                    ),
                ),
            ),
            spacing="2", width="100%", padding_top="0.5rem",
        ),
        rx.fragment(),
    )


def _biomass_panel() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AppState.biomass_busy,
            rx.center(
                rx.vstack(
                    rx.spinner(size="2"),
                    rx.text(AppState.tr["biomass_running"], size="1", color_scheme="gray"),
                    spacing="2", align="center",
                ),
                height="280px", width="100%",
            ),
            rx.cond(
                # biomass_error is only ever set by the single-point path
                # (run_analysis) — same reasoning as landscape_metrics_error.
                (AppState.biomass_error != "") & ~AppState.multi_mode,
                rx.callout(AppState.biomass_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.cond(
                    AppState.biomass_has_result,
                    _chart_box(AppState.biomass_figure, "nm-plot-biomass",
                              "naturametrics_biomassa",
                              ["260px", "280px", "280px", "280px"]),
                    rx.text(AppState.tr["biomass_empty"], size="1", color_scheme="gray"),
                ),
            ),
        ),
        rx.text(AppState.biomass_provenance_line, size="1", color_scheme="gray"),
        spacing="2", width="100%",
    )


def _ibge_comparison_panel() -> rx.Component:
    """IBGE Vegetação 2022 x MapBiomas 2022 — a QC cross-tabulation, not a
    time series, so unlike _biomass_panel it leads with two headline numbers
    (forest %, natural % per dataset) above the heatmap rather than a bare
    figure."""
    return rx.vstack(
        rx.cond(
            AppState.veg_compare_busy,
            rx.center(
                rx.vstack(
                    rx.spinner(size="2"),
                    rx.text(AppState.tr["ibge_veg_running"], size="1", color_scheme="gray"),
                    spacing="2", align="center",
                ),
                height="280px", width="100%",
            ),
            rx.cond(
                (AppState.veg_compare_error != "") & ~AppState.multi_mode,
                rx.callout(AppState.veg_compare_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.cond(
                    AppState.veg_compare_has_result,
                    rx.vstack(
                        rx.hstack(
                            rx.badge(AppState.veg_compare_forest_label,
                                     size="2", variant="soft", color_scheme="green"),
                            rx.badge(AppState.veg_compare_natural_label,
                                     size="2", variant="soft", color_scheme="grass"),
                            spacing="2", wrap="wrap",
                        ),
                        _chart_box(AppState.veg_compare_figure, "nm-plot-ibge",
                                  "naturametrics_ibge_x_mapbiomas",
                                  ["340px", "380px", "380px", "380px"]),
                        spacing="2", width="100%",
                    ),
                    rx.text(AppState.tr["ibge_veg_empty"], size="1", color_scheme="gray"),
                ),
            ),
        ),
        rx.text(AppState.tr["ibge_veg_caveat"], size="1", color_scheme="gray"),
        rx.text(AppState.veg_compare_provenance_line, size="1", color_scheme="gray"),
        spacing="2", width="100%",
    )


def _age_body() -> rx.Component:
    return rx.cond(
        AppState.age_running | AppState.multi_bbox_loading,
        rx.center(
            rx.vstack(
                rx.spinner(size="2"),
                rx.text(AppState.tr["age_running"],
                        size="1", color_scheme="gray"),
                spacing="2", align="center",
            ),
            height="280px", width="100%",
        ),
        rx.cond(
            AppState.age_error != "",
            rx.callout(AppState.age_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.cond(
                AppState.age_has_result,
                rx.cond(
                    AppState.age_showing_point,
                    _chart_box(AppState.age_point_figure, "nm-plot-age-point",
                              "naturametrics_idade_vegetacao_ponto",
                              ["260px", "280px", "280px", "280px"]),
                    rx.flex(
                        _chart_box(
                            AppState.age_histogram_figure, "nm-plot-age-hist",
                            "naturametrics_idade_vegetacao_histograma",
                            ["260px", "280px", "280px", "280px"],
                            box_props={
                                "flex": ["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                                "min_width": "0",
                            },
                        ),
                        rx.cond(
                            AppState.age_has_summary,
                            _age_summary_line(AppState.age_summary_row),
                            rx.fragment(),
                        ),
                        width="100%",
                        direction=rx.breakpoints(initial="column", lg="row"),
                        gap="1rem", align="start",
                    ),
                ),
                rx.fragment(),
            ),
        ),
    )


def _forest_age_panel() -> rx.Component:
    return rx.tabs.root(
        rx.vstack(
            # --- header ---------------------------------------------- #
            rx.flex(
                rx.hstack(
                    rx.icon("trees", size=15, color="var(--jade-11)"),
                    rx.tabs.list(
                        rx.tabs.trigger(AppState.tr["vegetation_age_title"],
                                       value="age"),
                        rx.tabs.trigger(AppState.tr["landscape_metrics_tab"],
                                        value="metrics"),
                        rx.tabs.trigger(AppState.tr["biomass_tab"],
                                        value="biomass"),
                        rx.tabs.trigger(AppState.tr["ibge_veg_tab"],
                                        value="ibge_compare"),
                    ),
                    spacing="2", align="center",
                    flex=["1 1 100%", "1 1 100%", "1 1 auto", "1 1 auto"],
                    min_width="0",
                ),
                rx.hstack(
                    rx.cond(AppState.multi_active, _multi_view_toggle(), rx.fragment()),
                    # The radius selector and its caption mean something for
                    # the age and biomass tabs (both read one buffer at a
                    # time) but not for metrics, which already lists every
                    # radius as its own row (landscape_metrics_rows).
                    rx.cond(
                        (AppState.selected_age_view == "age")
                        | (AppState.selected_age_view == "biomass")
                        | (AppState.selected_age_view == "ibge_compare"),
                        rx.fragment(
                            rx.cond(
                                AppState.region_mode_active,
                                rx.badge(AppState.region_mode_label, size="1",
                                         variant="soft", color_scheme="gray"),
                                rx.segmented_control.root(
                                    rx.foreach(
                                        AppState.age_tab_options,
                                        lambda opt: rx.segmented_control.item(
                                            opt, value=opt),
                                    ),
                                    value=AppState.selected_age_radius,
                                    on_change=AppState.set_selected_age_radius,
                                    size="1",
                                ),
                            ),
                            rx.cond(
                                ~AppState.geometry_active,
                                rx.text(AppState.buffer_extent_caption, size="1",
                                        color_scheme="gray", white_space="nowrap"),
                                rx.fragment(),
                            ),
                        ),
                        rx.fragment(),
                    ),
                    spacing="2", align="center",
                ),
                width="100%", align="center", justify="between",
                wrap="wrap", gap="0.5rem",
            ),

            # --- body ------------------------------------------------ #
            rx.tabs.content(_age_body(), value="age", width="100%"),
            rx.tabs.content(_landscape_metrics_panel(), value="metrics", width="100%"),
            rx.tabs.content(_biomass_panel(), value="biomass", width="100%"),
            rx.tabs.content(_ibge_comparison_panel(), value="ibge_compare", width="100%"),
            rx.cond(
                AppState.selected_age_view == "age",
                rx.text(AppState.age_provenance_line, size="1", color_scheme="gray"),
                rx.fragment(),
            ),
            width="100%", spacing="3", align_items="stretch",
        ),
        value=AppState.selected_age_view,
        on_change=AppState.set_selected_age_view,
        width="100%",
    )


def results_drawer() -> rx.Component:
    return rx.box(
        rx.cond(
            AppState.has_subject | AppState.analysis_running | AppState.multi_active,
            rx.flex(
                rx.box(_land_use_panel(), flex="1 1 50%", min_width="0"),
                rx.box(_forest_age_panel(), flex="1 1 50%", min_width="0",
                       border_left=["none", "none", "none", "1px solid var(--gray-5)"],
                       padding_left=["0", "0", "0", "1rem"]),
                width="100%", align="start", gap="1rem",
                direction=rx.breakpoints(initial="column", lg="row"),
                padding=["0.6rem 0.7rem", "0.6rem 0.75rem", "0.75rem 1rem", "0.75rem 1rem"],
            ),
            # Empty state. Without it the area under the map is blank white,
            # which reads as a loading failure rather than "nothing chosen yet".
            rx.center(
                rx.vstack(
                    rx.icon("map-pin", size=22, color="var(--gray-8)"),
                    rx.text(AppState.tr["empty_state_title"],
                            size="2", weight="medium", color_scheme="gray"),
                    rx.text(
                        AppState.tr["empty_state_body"],
                        size="1", color_scheme="gray", text_align="center",
                        style={"maxWidth": "34ch"},
                    ),
                    spacing="2", align="center",
                ),
                width="100%",
                padding=["1.5rem 1rem", "1.5rem 1rem", "2rem 1rem", "2rem 1rem"],
            ),
        ),
        width="100%",
        border_top="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        # Only the desktop drawer is height-capped and independently scrollable;
        # below that it is just the bottom of the page's single scroll column.
        max_height=["none", "none", "none", "50vh"],
        overflow_y=["visible", "visible", "visible", "auto"],
        flex_shrink="0",
    )
