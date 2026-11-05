"""Results drawer for the USA page: land cover (NLCD) and forest change (Hansen).

Two panels, each with its own header, body and error state, so a Hansen failure never
blanks a land-cover answer that is already on screen.
"""

from __future__ import annotations

import reflex as rx

from ...components.panel_kit import biomass_panel, metrics_panel, right_tabs

from .gbif_panel import gbif_buffer_panel
from ..state import USState as S


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
                    S.nlcd_has_data,
                    rx.flex(
                        rx.box(
                            # More height below "lg" than desktop's 340px,
                            # not less — see the main app's own results.py
                            # for the full rationale: the figure's own
                            # legend (charts.py's _style()) wraps to more
                            # rows on the exact widths that used to get
                            # less room, and config.responsive resizes the
                            # plot to match this box's rendered height, not
                            # the figure's own layout.height.
                            rx.plotly(
                                data=S.history_figure,
                                config={"displayModeBar": False,
                                        "displaylogo": False, "responsive": True},
                                width="100%",
                                height=["400px", "400px", "360px", "340px"],
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
                    rx.cond(
                        S.has_result,
                        rx.text(S.tr["nlcd_empty"], size="1", color_scheme="gray",
                                style={"maxWidth": "60ch"}),
                        rx.fragment(),
                    ),
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
            S.forest_error != "",
            rx.callout(S.forest_error, icon="triangle-alert",
                       color_scheme="amber", size="1", width="100%"),
            rx.fragment(),
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


def _panel(icon: str, title, hint, running, error, has, figure, extra=None, empty_note=None,
           attribution=None) -> rx.Component:
    """One analysis panel with its own header, running line, error and body."""
    return rx.vstack(
        rx.hstack(rx.icon(icon, size=15, color="var(--jade-11)"),
                  rx.text(title, size="2", weight="bold", white_space="nowrap"),
                  rx.cond(running, rx.spinner(size="1"), rx.fragment()),
                  spacing="2", align="center", width="100%"),
        rx.text(hint, size="1", color_scheme="gray"),
        rx.cond(error != "",
                rx.callout(error, icon="triangle-alert", color_scheme="amber", size="1", width="100%"),
                rx.fragment()),
        rx.cond(has,
                rx.vstack(
                    rx.plotly(data=figure, config={"displayModeBar": False, "displaylogo": False,
                                                   "responsive": True}, width="100%"),
                    *( [extra] if extra is not None else [] ),
                    spacing="2", width="100%", align_items="stretch"),
                rx.cond(empty_note is not None and ~running & (error == ""),
                        rx.text(empty_note, size="1", color_scheme="gray") if empty_note is not None
                        else rx.fragment(), rx.fragment())),
        rx.cond(attribution is not None, rx.text(attribution, size="1", color_scheme="gray")
                if attribution is not None else rx.fragment(), rx.fragment()),
        width="100%", spacing="2", align_items="stretch")


def _tab_dist() -> rx.Component:
    return _panel("flame", S.tr["dist_title"], S.tr["dist_hint"], S.dist_running, S.dist_error,
                  S.dist_has_data, S.dist_figure, empty_note=S.tr["dist_empty"],
                  attribution=S.tr["dist_attribution"])


def _tab_age() -> rx.Component:
    age_stats = rx.hstack(
        rx.foreach(S.age_summary_rows, lambda r: rx.vstack(
            rx.text(r["label"], size="1", color_scheme="gray"),
            rx.text(r["value"], size="2", weight="medium"), spacing="0", align_items="start")),
        spacing="5", wrap="wrap")
    return _panel("hourglass", S.tr["age_title"], S.tr["age_hint"], S.age_running, S.age_error,
                  S.age_has_data, S.age_figure, extra=age_stats, empty_note=S.tr["age_empty"],
                  attribution=S.tr["age_attribution"])


def _tab_fire() -> rx.Component:
    return _panel("siren", S.tr["fire_title"], S.tr["fire_hint"], S.fire_running, S.fire_error,
                  S.fire_has_data, S.fire_figure, empty_note=S.tr["fire_empty"],
                  attribution=S.tr["fire_attribution"])


def _tab_canopy() -> rx.Component:
    return _panel("trees", S.tr["canopy_title"], S.tr["canopy_hint"], S.canopy_running,
                  S.canopy_error, S.canopy_has_data, S.canopy_figure,
                  attribution=S.tr["canopy_attribution"])


def _gbif_species_panel() -> rx.Component:
    """Species already recorded (GBIF) around the study point.

    Full width and below the two-column row rather than sharing either
    column: the Brazil page gives this the same reason for being its own
    tab rather than living in the sidebar — a species table needs the
    results area's width, not a 320px-equivalent half-column.
    """
    return rx.vstack(
        rx.hstack(
            rx.icon("bug", size=15, color="var(--jade-11)"),
            rx.text(S.tr["gbif_species_tab"], size="2", weight="bold",
                    white_space="nowrap"),
            spacing="2", align="center", width="100%",
        ),
        rx.text(S.tr["gbif_species_tab_hint"], size="1", color_scheme="gray"),
        gbif_buffer_panel(),
        width="100%", spacing="3", align_items="stretch",
    )


def _resize_button() -> rx.Component:
    """Desktop-only: see the Brazil page's own ``components/results.py::
    _resize_button`` for the full rationale."""
    return rx.box(
        rx.tooltip(
            rx.button(
                rx.icon("unfold-vertical", size=14),
                rx.text(S.tr["results_resize_label"], size="1"),
                on_click=S.cycle_results_panel_size,
                size="1", variant="solid", color_scheme="gray",
                aria_label=S.tr["results_resize_aria"],
            ),
            content=S.tr["results_resize_hint"],
        ),
        position="absolute", top="0.4rem", right="0.6rem", z_index="1",
        display=["none", "none", "none", "flex"],
    )


def results_drawer() -> rx.Component:
    """Two columns, matching the Brazil drawer's shape.

    Land cover (NLCD, 41 stacked columns with a legend) takes the left half; forest
    change takes the right.

    Below the desktop breakpoint the row becomes a column and the panels simply
    stack, which is the only thing that fits on a phone. The GBIF
    species panel runs full-width beneath both columns rather than inside
    either — see ``_gbif_species_panel()``.
    """
    return rx.box(
        _resize_button(),
        rx.cond(
            S.has_point | S.analysis_running,
            rx.fragment(
                rx.flex(
                    rx.box(_land_cover_panel(), flex="1 1 50%", min_width="0"),
                    rx.box(
                        right_tabs([
                            ("dist", S.tr["tab_dist"], _tab_dist()),
                            ("age", S.tr["tab_age"], _tab_age()),
                            ("fire", S.tr["tab_fire"], _tab_fire()),
                            ("canopy", S.tr["tab_canopy"], _tab_canopy()),
                            ("forest", S.tr["tab_forest"], _forest_change_panel()),
                            ("metrics", S.tr["tab_metrics"], metrics_panel(S)),
                            ("biomass", S.tr["tab_biomass"], biomass_panel(S)),
                            ("species", S.tr["tab_species"], _gbif_species_panel()),
                        ]),
                        flex="1 1 50%", min_width="0",
                        border_left=["none", "none", "none", "1px solid var(--gray-5)"],
                        padding_left=["0", "0", "0", "1rem"],
                    ),
                    width="100%", align="start", gap="1rem",
                    direction=rx.breakpoints(initial="column", lg="row"),
                    padding=["0.6rem 0.7rem", "0.6rem 0.75rem", "0.75rem 1rem",
                             "0.75rem 1rem"],
                ),
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
        position="relative",
        max_height=["none", "none", "none", S.results_panel_height],
        overflow_y=["visible", "visible", "visible", "auto"],
        flex_shrink="0",
    )
