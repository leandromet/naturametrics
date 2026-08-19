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
            AppState.has_point | AppState.analysis_running | AppState.multi_active,
            rx.vstack(
                # --- header ---------------------------------------------- #
                # Wraps instead of overflowing: on a phone the title, the
                # coordinate badge and the radius control cannot share one row.
                rx.flex(
                    rx.hstack(
                        rx.icon("chart-column", size=15, color="var(--jade-11)"),
                        rx.text("História de uso da terra", size="2", weight="bold",
                                white_space="nowrap"),
                        # The coordinate is already shown in the side panel, so
                        # on a phone it is dropped rather than allowed to collide
                        # with the radius control.
                        rx.cond(
                            AppState.multi_active,
                            rx.badge(AppState.multi_label, variant="soft", size="1",
                                     color_scheme="jade"),
                            rx.cond(
                                AppState.point_label != "",
                                rx.badge(AppState.point_label, variant="soft",
                                         size="1",
                                         display=["none", "none", "inline-flex",
                                                  "inline-flex"]),
                                rx.fragment(),
                            ),
                        ),
                        # Second entry point to the same dialog as the header
                        # button: this is where the user is looking when they
                        # decide they want the numbers behind the chart.
                        rx.cond(
                            AppState.has_result | AppState.multi_active,
                            rx.button(
                                rx.icon("download", size=13),
                                rx.text("Baixar dados", size="1"),
                                on_click=AppState.set_export_open(True),
                                size="1", variant="ghost", color_scheme="jade",
                                aria_label="Baixar dados deste ponto",
                            ),
                            rx.fragment(),
                        ),
                        spacing="2", align="center",
                        # Full-width line on phone, shares the row from tablet up.
                        flex=["1 1 100%", "1 1 100%", "1 1 auto", "1 1 auto"],
                        min_width="0",
                    ),
                    rx.hstack(
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
                        spacing="2", align="center",
                    ),
                    width="100%", align="center", justify="between",
                    wrap="wrap", gap="0.5rem",
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
                            rx.flex(
                                rx.box(
                                    rx.plotly(
                                        data=AppState.history_figure,
                                        # The modebar is hover-revealed on desktop
                                        # but permanently visible on touch, where
                                        # it sits on top of the plot. Chart export
                                        # is a planned feature of our own, so
                                        # nothing is lost by removing it.
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
                                    spacing="2",
                                    width=["100%", "100%", "100%", "270px"],
                                    flex_shrink=["1", "1", "1", "0"],
                                    align_items="stretch",
                                    height=["auto", "auto", "auto", "340px"],
                                ),
                                width="100%",
                                # Typed literal props need rx.breakpoints(); a
                                # plain list only works for style props.
                                direction=rx.breakpoints(initial="column", lg="row"),
                                gap="1rem", align="start",
                            ),
                            rx.fragment(),
                        ),
                    ),
                ),
                width="100%", spacing="3",
                padding=["0.6rem 0.7rem", "0.6rem 0.75rem", "0.75rem 1rem", "0.75rem 1rem"],
            ),
            # Empty state. Without it the area under the map is blank white,
            # which reads as a loading failure rather than "nothing chosen yet".
            rx.center(
                rx.vstack(
                    rx.icon("map-pin", size=22, color="var(--gray-8)"),
                    rx.text("Clique no mapa para escolher um ponto",
                            size="2", weight="medium", color_scheme="gray"),
                    rx.text(
                        "A história de uso da terra de 1985 a 2024 será calculada "
                        "para raios de 1, 2, 5 e 10 km em volta dele.",
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
        max_height=["none", "none", "none", "46vh"],
        overflow_y=["visible", "visible", "visible", "auto"],
        flex_shrink="0",
    )
