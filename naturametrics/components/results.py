"""Results drawer: the land-cover history chart and its summary."""

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


def results_drawer() -> rx.Component:
    return rx.box(
        rx.cond(
            AppState.has_point | AppState.analysis_running,
            rx.vstack(
                # --- header ---------------------------------------------- #
                rx.hstack(
                    rx.icon("chart-column", size=15, color="var(--jade-11)"),
                    rx.text("História de uso da terra", size="2", weight="bold"),
                    rx.cond(
                        AppState.point_label != "",
                        rx.badge(AppState.point_label, variant="soft", size="1"),
                        rx.fragment(),
                    ),
                    rx.spacer(),
                    rx.segmented_control.root(
                        rx.foreach(
                            AppState.radius_options,
                            lambda opt: rx.segmented_control.item(opt, value=opt),
                        ),
                        value=AppState.selected_radius_label,
                        on_change=AppState.set_selected_radius,
                        size="1",
                    ),
                    rx.hstack(
                        rx.switch(checked=AppState.normalise_chart,
                                  on_change=AppState.toggle_normalise, size="1"),
                        rx.text("%", size="1", color_scheme="gray"),
                        spacing="1", align="center",
                    ),
                    width="100%", align="center", spacing="3",
                ),

                # --- body ------------------------------------------------ #
                rx.cond(
                    AppState.analysis_running,
                    rx.center(
                        rx.vstack(
                            rx.spinner(size="2"),
                            rx.text("Reduzindo 40 anos sobre 4 buffers…",
                                    size="1", color_scheme="gray"),
                            spacing="2", align="center",
                        ),
                        height="300px", width="100%",
                    ),
                    rx.cond(
                        AppState.analysis_error != "",
                        rx.callout(AppState.analysis_error, icon="triangle-alert",
                                   color_scheme="amber", size="1", width="100%"),
                        rx.cond(
                            AppState.has_result,
                            rx.hstack(
                                rx.box(
                                    rx.plotly(data=AppState.history_figure,
                                              width="100%", height="340px"),
                                    flex="1", min_width="0",
                                ),
                                rx.vstack(
                                    rx.text(
                                        "Classes principais (2024)",
                                        size="1", weight="bold",
                                        color_scheme="gray",
                                        style={"textTransform": "uppercase",
                                               "letterSpacing": "0.06em"},
                                    ),
                                    rx.foreach(AppState.summary_rows, _legend_row),
                                    rx.spacer(),
                                    rx.text(AppState.provenance_line, size="1",
                                            color_scheme="gray"),
                                    spacing="2", width="270px", flex_shrink="0",
                                    align_items="stretch", height="340px",
                                ),
                                width="100%", spacing="4", align_items="start",
                            ),
                            rx.fragment(),
                        ),
                    ),
                ),
                width="100%", spacing="3", padding="0.75rem 1rem",
            ),
            rx.fragment(),
        ),
        width="100%",
        border_top="1px solid var(--gray-5)",
        background="var(--color-panel-solid)",
        max_height="46vh",
        overflow_y="auto",
        flex_shrink="0",
    )
