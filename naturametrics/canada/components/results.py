"""Results drawer for the Canada page: crop inventory, forest age, forest change.

Three panels rather than Brazil's two, and each keeps its own header, body and
error state. That separation is load-bearing here: north of the AAFC extent the
first panel legitimately has nothing while the other two are full, and a shared
empty state would misreport that as a failure.
"""

from __future__ import annotations

import reflex as rx

from ..state import CanadaState as S


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


def _stat_row(row: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px",
               background=row["color"], flex_shrink="0"),
        rx.text(row["label"], size="1", flex="1"),
        rx.text(row["value"], size="1", weight="medium"),
        spacing="2", align="center", width="100%",
    )


def _radius_switcher() -> rx.Component:
    return rx.hstack(
        rx.segmented_control.root(
            rx.foreach(S.radius_options,
                       lambda opt: rx.segmented_control.item(opt, value=opt)),
            value=S.selected_radius_label,
            on_change=S.set_selected_radius,
            size="1",
        ),
        rx.hstack(
            rx.switch(checked=S.normalise_chart, on_change=S.toggle_normalise,
                      size="1"),
            rx.text("%", size="1", color_scheme="gray"),
            spacing="1", align="center",
        ),
        spacing="2", align="center",
    )


def _land_cover_panel() -> rx.Component:
    return rx.vstack(
        rx.flex(
            rx.hstack(
                rx.icon("chart-column", size=15, color="var(--jade-11)"),
                rx.text(S.tr["landuse_title"], size="2", weight="bold",
                        white_space="nowrap"),
                rx.cond(
                    S.point_label != "",
                    rx.badge(S.point_label, variant="soft", size="1",
                             display=["none", "none", "inline-flex", "inline-flex"]),
                    rx.fragment(),
                ),
                rx.cond(
                    S.has_result,
                    rx.button(
                        rx.icon("download", size=13),
                        rx.text(S.tr["download_button"], size="1"),
                        on_click=S.set_export_open(True),
                        size="1", variant="ghost", color_scheme="jade",
                    ),
                    rx.fragment(),
                ),
                spacing="2", align="center",
                flex=["1 1 100%", "1 1 100%", "1 1 auto", "1 1 auto"],
                min_width="0",
            ),
            _radius_switcher(),
            width="100%", align="center", justify="between",
            wrap="wrap", gap="0.5rem",
        ),
        rx.cond(
            S.analysis_running,
            rx.center(
                rx.vstack(rx.spinner(size="2"),
                          rx.text(S.tr["analysis_running"], size="1",
                                  color_scheme="gray"),
                          spacing="2", align="center"),
                height="300px", width="100%",
            ),
            rx.cond(
                S.analysis_error != "",
                rx.callout(S.analysis_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.cond(
                    S.aci_has_data,
                    rx.flex(
                        rx.box(
                            rx.plotly(
                                data=S.history_figure,
                                config={"displayModeBar": False,
                                        "displaylogo": False, "responsive": True},
                                width="100%",
                                height=["300px", "320px", "340px", "340px"],
                            ),
                            flex=["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                            min_width="0", width="100%",
                        ),
                        rx.vstack(
                            rx.text(S.top_classes_title, size="1",
                                    weight="bold", color_scheme="gray",
                                    style={"textTransform": "uppercase",
                                           "letterSpacing": "0.06em"}),
                            rx.foreach(S.summary_rows, _legend_row),
                            rx.spacer(),
                            rx.text(S.provenance_line, size="1", color_scheme="gray"),
                            spacing="2",
                            width=["100%", "100%", "100%", "230px"],
                            flex_shrink=["1", "1", "1", "0"],
                            align_items="stretch",
                            height=["auto", "auto", "auto", "340px"],
                        ),
                        width="100%",
                        direction=rx.breakpoints(initial="column", lg="row"),
                        gap="1rem", align="start",
                    ),
                    # The Canadian empty state: the analysis worked, this
                    # particular product just does not reach here.
                    rx.cond(
                        S.has_result,
                        rx.center(
                            rx.vstack(
                                rx.icon("map-pinned", size=20,
                                        color="var(--amber-9)"),
                                rx.text(S.tr["aci_empty_title"], size="2",
                                        weight="medium", color_scheme="gray"),
                                rx.text(S.tr["aci_north_warning"], size="1",
                                        color_scheme="gray", text_align="center",
                                        style={"maxWidth": "44ch"}),
                                spacing="2", align="center",
                            ),
                            width="100%", padding="2rem 1rem",
                        ),
                        rx.fragment(),
                    ),
                ),
            ),
        ),
        width="100%", spacing="3", align_items="stretch",
    )


def _forest_age_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("trees", size=15, color="var(--jade-11)"),
            rx.text(S.tr["forest_age_title"], size="2", weight="bold",
                    white_space="nowrap"),
            spacing="2", align="center", width="100%",
        ),
        rx.cond(
            S.age_running,
            rx.center(
                rx.vstack(rx.spinner(size="2"),
                          rx.text(S.tr["age_running"], size="1",
                                  color_scheme="gray"),
                          spacing="2", align="center"),
                height="170px", width="100%",
            ),
            rx.cond(
                S.age_error != "",
                rx.callout(S.age_error, icon="triangle-alert",
                           color_scheme="amber", size="1", width="100%"),
                rx.cond(
                    S.age_has_result,
                    rx.flex(
                        rx.box(
                            rx.plotly(
                                data=S.age_histogram_figure,
                                config={"displayModeBar": False,
                                        "displaylogo": False, "responsive": True},
                                width="100%", height="180px",
                            ),
                            flex=["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                            min_width="0", width="100%",
                        ),
                        rx.cond(
                            S.age_has_summary,
                            rx.vstack(
                                rx.hstack(
                                    rx.text(S.tr["age_median_label"], size="1",
                                            color_scheme="gray"),
                                    rx.spacer(),
                                    rx.text(S.age_summary_row["median_bin"],
                                            size="1", weight="medium"),
                                    width="100%",
                                ),
                                rx.hstack(
                                    rx.text(S.tr["age_forest_area_label"], size="1",
                                            color_scheme="gray"),
                                    rx.spacer(),
                                    rx.text(S.age_summary_row["forest_area"],
                                            size="1", weight="medium"),
                                    width="100%",
                                ),
                                rx.hstack(
                                    rx.text(S.tr["age_forest_pct_label"], size="1",
                                            color_scheme="gray"),
                                    rx.spacer(),
                                    rx.text(S.age_summary_row["forest_pct"],
                                            size="1", weight="medium"),
                                    width="100%",
                                ),
                                rx.divider(),
                                rx.hstack(
                                    rx.text(S.tr["age_point_label"], size="1",
                                            color_scheme="gray"),
                                    rx.spacer(),
                                    rx.text(S.age_point_label, size="1",
                                            weight="medium"),
                                    width="100%",
                                ),
                                rx.text(S.age_reference_note, size="1",
                                        color_scheme="gray"),
                                spacing="1",
                                width=["100%", "100%", "100%", "175px"],
                                flex_shrink=["1", "1", "1", "0"],
                                align_items="stretch",
                            ),
                            rx.fragment(),
                        ),
                        width="100%",
                        direction=rx.breakpoints(initial="column", lg="row"),
                        gap="1rem", align="start",
                    ),
                    rx.fragment(),
                ),
            ),
        ),
        width="100%", spacing="3", align_items="stretch",
    )


def _forest_change_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("trending-down", size=15, color="var(--jade-11)"),
            rx.text(S.change_title, size="2", weight="bold", white_space="nowrap"),
            spacing="2", align="center", width="100%",
        ),
        rx.cond(
            S.change_has_data,
            rx.flex(
                rx.box(
                    rx.plotly(
                        data=S.loss_figure,
                        config={"displayModeBar": False, "displaylogo": False,
                                "responsive": True},
                        width="100%", height="150px",
                    ),
                    flex=["1 1 100%", "1 1 100%", "1 1 100%", "1 1 0"],
                    min_width="0", width="100%",
                ),
                rx.vstack(
                    rx.foreach(S.change_rows, _stat_row),
                    # Why the green is a level and not a line. Without this the
                    # dashed gain reference looks like a chart the app failed to
                    # finish drawing, rather than the shape of the data.
                    rx.text(S.tr["change_gain_undated_note"], size="1",
                            color_scheme="gray", style={"lineHeight": "1.35"}),
                    spacing="2",
                    width=["100%", "100%", "100%", "175px"],
                    flex_shrink=["1", "1", "1", "0"],
                    align_items="stretch",
                ),
                width="100%",
                direction=rx.breakpoints(initial="column", lg="row"),
                gap="1rem", align="start",
            ),
            rx.fragment(),
        ),
        width="100%", spacing="3", align_items="stretch",
    )


def results_drawer() -> rx.Component:
    """Two columns, matching the Brazil drawer's shape.

    Crop inventory takes the whole left half; the two forest panels stack in the
    right half, change above age. The land-cover chart is the tall one — 17
    stacked columns with a legend — so pairing it with two short panels keeps
    both columns about the same height and the drawer off the rest of the screen.

    Below the desktop breakpoint the row becomes a column and the three panels
    simply stack, which is the only thing that fits on a phone.
    """
    return rx.box(
        rx.cond(
            S.has_point | S.analysis_running,
            rx.flex(
                rx.box(_land_cover_panel(), flex="1 1 50%", min_width="0"),
                rx.vstack(
                    _forest_change_panel(),
                    rx.divider(),
                    _forest_age_panel(),
                    spacing="3", align_items="stretch",
                    flex="1 1 50%", min_width="0",
                    border_left=["none", "none", "none",
                                 "1px solid var(--gray-5)"],
                    padding_left=["0", "0", "0", "1rem"],
                ),
                width="100%", align="start", gap="1rem",
                direction=rx.breakpoints(initial="column", lg="row"),
                padding=["0.6rem 0.7rem", "0.6rem 0.75rem", "0.75rem 1rem",
                         "0.75rem 1rem"],
            ),
            rx.center(
                rx.vstack(
                    rx.icon("map-pin", size=22, color="var(--gray-8)"),
                    rx.text(S.tr["empty_state_title"], size="2", weight="medium",
                            color_scheme="gray"),
                    rx.text(S.tr["empty_state_body"], size="1", color_scheme="gray",
                            text_align="center", style={"maxWidth": "40ch"}),
                    spacing="2", align="center",
                ),
                width="100%",
                padding=["1.5rem 1rem", "1.5rem 1rem", "2rem 1rem", "2rem 1rem"],
            ),
        ),
        width="100%",
        border_top="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        max_height=["none", "none", "none", "55vh"],
        overflow_y=["visible", "visible", "visible", "auto"],
        flex_shrink="0",
    )
