"""Results drawer: land-cover history and forest age, side by side.

The two halves are deliberately separate components (doc/10-forest-age.md): they
answer different questions from related but distinct MapBiomas products, and
keeping their own header/body/provenance line each means one failing (e.g. the DSV
asset above having a hiccup) never blanks the other.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState


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
            AppState.multi_bbox_loading,
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
                rx.cond(
                    AppState.multi_active,
                    rx.fragment(),
                    rx.segmented_control.root(
                        rx.segmented_control.item(
                            AppState.tr["vegetation_age_title"], value="age"),
                        rx.segmented_control.item(
                            AppState.tr["landscape_metrics_tab"], value="metrics"),
                        value=AppState.selected_age_view,
                        on_change=AppState.set_selected_age_view,
                        size="1",
                    ),
                ),
                rx.cond(AppState.multi_active, _multi_view_toggle(), rx.fragment()),
                rx.cond(
                    AppState.full_area_active,
                    rx.badge(AppState.full_area_radius_label, size="1",
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
                rx.text(AppState.buffer_extent_caption, size="1", color_scheme="gray",
                        white_space="nowrap"),
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
                        rx.box(
                            rx.plotly(
                                data=AppState.history_figure,
                                # The modebar is hover-revealed on desktop but
                                # permanently visible on touch, where it sits on
                                # top of the plot. Chart export is a planned
                                # feature of our own, so nothing is lost by
                                # removing it.
                                config={"displayModeBar": False,
                                        "displaylogo": False,
                                        "responsive": True},
                                width="100%",
                                height=["300px", "320px", "340px", "340px"],
                            ),
                            flex=["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                            min_width="0", width="100%",
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
                rx.plotly(
                    data=AppState.change_figure,
                    config={"displayModeBar": False, "displaylogo": False,
                            "responsive": True},
                    width="100%", height="150px",
                ),
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
        rx.text(row["shannon"], size="1"),
        rx.text(row["simpson"], size="1"),
        rx.text(row["evenness"], size="1"),
        columns="repeat(8, minmax(0, 1fr))",
        gap="0.4rem", width="100%",
    )


def _landscape_metrics_panel() -> rx.Component:
    return rx.vstack(
        rx.text(AppState.tr["landscape_metrics_tab"], size="2", weight="bold"),
        rx.text(
            "NP · PD · LPI · ED · Shannon · Simpson",
            size="1", color_scheme="gray",
        ),
        rx.grid(
            *[rx.text(AppState.tr[key], size="1", weight="bold") for key in (
                "metrics_buffer", "metrics_patches", "metrics_patch_density",
                "metrics_lpi", "metrics_edge_density", "metrics_shannon",
                "metrics_simpson", "metrics_evenness")],
            columns="repeat(8, minmax(0, 1fr))",
            gap="0.4rem", width="100%",
        ),
        rx.cond(
            AppState.landscape_metrics_running,
            rx.spinner(size="1"),
            rx.cond(
                AppState.landscape_metrics_error != "",
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
        rx.text(AppState.provenance_line, size="1", color_scheme="gray"),
        spacing="2", width="100%", overflow_x="auto",
    )


def _forest_age_panel() -> rx.Component:
    return rx.vstack(
        # --- header ---------------------------------------------- #
        rx.flex(
            rx.hstack(
                rx.icon("trees", size=15, color="var(--jade-11)"),
                rx.text(AppState.tr["vegetation_age_title"], size="2", weight="bold",
                        white_space="nowrap"),
                spacing="2", align="center",
                flex=["1 1 100%", "1 1 100%", "1 1 auto", "1 1 auto"],
                min_width="0",
            ),
            rx.hstack(
                rx.cond(AppState.multi_active, _multi_view_toggle(), rx.fragment()),
                rx.cond(
                    AppState.full_area_active,
                    rx.badge(AppState.full_area_radius_label, size="1",
                             variant="soft", color_scheme="gray"),
                    rx.segmented_control.root(
                        rx.foreach(
                            AppState.age_tab_options,
                            lambda opt: rx.segmented_control.item(opt, value=opt),
                        ),
                        value=AppState.selected_age_radius,
                        on_change=AppState.set_selected_age_radius,
                        size="1",
                    ),
                ),
                rx.text(AppState.buffer_extent_caption, size="1", color_scheme="gray",
                        white_space="nowrap"),
                spacing="2", align="center",
            ),
            width="100%", align="center", justify="between",
            wrap="wrap", gap="0.5rem",
        ),

        # --- body ------------------------------------------------ #
        rx.cond(
            (AppState.selected_age_view == "metrics") & ~AppState.multi_active,
            _landscape_metrics_panel(),
            rx.cond(
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
                        rx.plotly(
                            data=AppState.age_point_figure,
                            config={"displayModeBar": False, "displaylogo": False,
                                    "responsive": True},
                            width="100%",
                            height=["260px", "280px", "280px", "280px"],
                        ),
                        rx.flex(
                            rx.box(
                                rx.plotly(
                                    data=AppState.age_histogram_figure,
                                    config={"displayModeBar": False,
                                            "displaylogo": False,
                                            "responsive": True},
                                    width="100%",
                                    height=["260px", "280px", "280px", "280px"],
                                ),
                                flex=["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                                min_width="0", width="100%",
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
            ),
        ),
        rx.text(AppState.age_provenance_line, size="1", color_scheme="gray"),
        width="100%", spacing="3", align_items="stretch",
    )


def results_drawer() -> rx.Component:
    return rx.box(
        rx.cond(
            AppState.has_point | AppState.analysis_running | AppState.multi_active,
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
