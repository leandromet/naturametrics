"""The download panel.

A dialog rather than another sidebar section, for the reason the user asked for:
the sidebar already carries five layer controls and a filter cascade, and an
export panel with a checklist inside it would push everything else below the
fold. It sits beside "Como usar" and "Como citar" in the header, which is where
the other things-you-open-and-close already live.

Both downloads are a single ODS file with one tab per table, metadata tab first.
See ``services/exports.py`` for why one spreadsheet and not a ZIP of CSVs.
"""

from __future__ import annotations

import reflex as rx

from ..config.settings import BUFFER_RADII_KM
from ..state import AppState
from ..translations import get_translations

_RADII = ", ".join(f"{r:g}" for r in sorted(BUFFER_RADII_KM))


def _tr_radii(key: str) -> rx.Var:
    """A translated string with ``{radii}`` filled in at build time.

    ``AppState.tr[key]`` is a runtime Var — Python's ``.format()`` cannot run
    on it in the component tree (only inside state methods, where ``self.tr``
    is the real dict). ``_RADII`` never changes, so both language variants can
    be formatted once here and switched with ``rx.cond``.
    """
    return rx.cond(
        AppState.language == "pt",
        get_translations("pt")[key].format(radii=_RADII),
        get_translations("en")[key].format(radii=_RADII),
    )


def _check(label: str, detail: str, checked, on_change,
           disabled=False) -> rx.Component:
    return rx.hstack(
        rx.checkbox(checked=checked, on_change=on_change, disabled=disabled,
                    size="2", color_scheme="jade", margin_top="2px"),
        rx.vstack(
            rx.text(label, size="2", weight="medium"),
            rx.text(detail, size="1", color_scheme="gray",
                    style={"lineHeight": "1.35"}),
            spacing="0", align_items="start",
        ),
        spacing="3", align_items="start", width="100%",
    )


def _study_point_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(AppState.tr["section_point"], size="2", weight="bold"),
            rx.spacer(),
            rx.cond(
                AppState.has_result,
                rx.badge(AppState.point_label, size="1", variant="soft",
                         color_scheme="jade"),
                rx.badge(AppState.tr["no_point_badge"], size="1", variant="soft",
                         color_scheme="gray"),
            ),
            width="100%", align="center",
        ),
        rx.cond(
            AppState.point_identity_label != "",
            rx.text(AppState.point_identity_label, size="1", color_scheme="gray"),
            rx.fragment(),
        ),
        rx.text(
            _tr_radii("study_point_desc"),
            size="1", color_scheme="gray", style={"lineHeight": "1.45"},
        ),
        rx.button(
            rx.icon("download", size=14),
            AppState.tr["download_point_button"],
            on_click=AppState.download_study_point,
            disabled=~AppState.has_result | AppState.export_busy,
            size="2", color_scheme="jade", width="100%",
        ),
        rx.cond(
            AppState.has_result,
            rx.fragment(),
            rx.text(AppState.tr["download_point_hint"],
                    size="1", color_scheme="gray"),
        ),
        rx.divider(),
        rx.text(AppState.tr["report_section_title"], size="2", weight="medium"),
        rx.text(AppState.tr["report_section_desc"], size="1", color_scheme="gray",
                style={"lineHeight": "1.4"}),
        _check(
            AppState.tr["check_report_figures_label"],
            AppState.tr["check_report_figures_detail"],
            AppState.exp_report_figures, AppState.toggle_exp_report_figures,
        ),
        _check(
            AppState.tr["check_report_tables_label"],
            AppState.tr["check_report_tables_detail"],
            AppState.exp_report_tables, AppState.toggle_exp_report_tables,
        ),
        rx.button(
            rx.icon("file-text", size=14),
            AppState.tr["download_report_button"],
            on_click=AppState.download_study_point_report,
            disabled=(~AppState.has_result | AppState.export_busy
                     | ~AppState.export_report_any),
            size="2", variant="soft", color_scheme="jade", width="100%",
        ),
        spacing="2", align_items="start", width="100%",
    )


def _selection_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                rx.cond(AppState.user_points_active,
                       AppState.tr["selection_title_submitted"],
                       AppState.tr["selection_title_default"]),
                size="2", weight="bold",
            ),
            rx.spacer(),
            rx.badge(AppState.export_count_label, size="1", variant="soft",
                     color_scheme="jade"),
            width="100%", align="center",
        ),
        rx.cond(
            AppState.export_manual_available,
            rx.segmented_control.root(
                rx.foreach(
                    AppState.export_source_options,
                    lambda opt: rx.segmented_control.item(opt, value=opt),
                ),
                value=AppState.export_source_value,
                on_change=AppState.set_export_source,
                size="1", width="100%",
            ),
            rx.fragment(),
        ),
        rx.text(AppState.export_selection_label, size="1", color_scheme="gray"),
        rx.text(
            AppState.tr["selection_note"],
            size="1", color_scheme="gray",
        ),
        rx.divider(),
        _check(
            AppState.tr["check_points_label"],
            AppState.tr["check_points_detail"],
            AppState.exp_points, AppState.toggle_exp_points,
        ),
        _check(
            AppState.tr["check_pixel_label"],
            AppState.tr["check_pixel_detail"],
            AppState.exp_pixel, AppState.toggle_exp_pixel,
        ),
        _check(
            _tr_radii("check_buffers_label"),
            AppState.tr["check_buffers_detail"],
            AppState.exp_buffers, AppState.toggle_exp_buffers,
            # Never disabled, even over the ceiling. Disabling it would hide the
            # radius selector below — which is the one control that makes a large
            # selection fit, so the remedy would be unreachable in exactly the
            # case that needs it. The download button refuses instead, and the
            # note says what to change.
        ),
        rx.cond(
            AppState.exp_buffers,
            rx.vstack(
                rx.text(AppState.tr["export_radii_label"], size="1", color_scheme="gray"),
                rx.select(
                    AppState.export_radius_options,
                    value=AppState.export_radius_value,
                    on_change=AppState.set_exp_radius,
                    size="2", width="100%",
                ),
                spacing="1", width="100%", padding_left="2rem",
            ),
            rx.fragment(),
        ),
        _check(
            AppState.tr["check_connectivity_label"],
            AppState.tr["check_connectivity_detail"],
            AppState.exp_connectivity, AppState.toggle_exp_connectivity,
        ),
        rx.cond(
            AppState.export_source == "manual",
            _check(
                AppState.tr["check_full_area_label"],
                AppState.tr["check_full_area_detail"],
                AppState.exp_full_area, AppState.toggle_exp_full_area,
            ),
            rx.fragment(),
        ),
        rx.cond(
            AppState.exp_buffers | AppState.exp_connectivity,
            rx.callout(
                AppState.export_buffer_note,
                # Amber is a warning about size, never a refusal: the export
                # runs either way. There is no size limit on a spreadsheet, and
                # inventing one would be enforcing a constraint that does not
                # exist.
                icon=rx.cond(AppState.export_buffer_heavy
                             | AppState.export_buffer_over_limit,
                             "triangle-alert", "clock"),
                size="1",
                color_scheme=rx.cond(
                    AppState.export_buffer_over_limit, "red",
                    rx.cond(AppState.export_buffer_heavy, "amber", "gray")),
                width="100%",
            ),
            rx.fragment(),
        ),
        # The friction step: a bulk export with buffers costs real Earth Engine
        # compute per click, so the first click asks rather than runs (see
        # state/_export.py request_selection_download and the security-audit
        # note in doc/13-abuse-control.md). Nothing below this is the actual
        # enforcement — that is services.abuse_control, checked server-side
        # inside download_selection regardless of how it was reached.
        rx.cond(
            AppState.export_confirm_pending,
            rx.vstack(
                rx.callout(
                    AppState.export_confirm_message,
                    icon="circle-alert", color_scheme="amber", size="1",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        AppState.tr["cancel_button"],
                        on_click=AppState.cancel_selection_download,
                        size="2", variant="soft", color_scheme="gray", flex="1",
                    ),
                    rx.button(
                        rx.icon("download", size=14), AppState.tr["confirm_download_button"],
                        on_click=AppState.download_selection,
                        size="2", color_scheme="jade", flex="1",
                    ),
                    spacing="2", width="100%",
                ),
                spacing="2", width="100%",
            ),
            rx.button(
                rx.icon("download", size=14),
                AppState.tr["download_selection_button"],
                on_click=AppState.request_selection_download,
                disabled=AppState.export_busy | AppState.export_nothing_selected
                         | (AppState.export_selection_count == 0)
                         # The only size-based refusal, and the remedy is the
                         # sidebar filters rather than anything in this panel — so
                         # the checkbox above stays usable and the note explains.
                         | ((AppState.exp_buffers | AppState.exp_connectivity)
                            & AppState.export_buffer_over_limit),
                size="2", color_scheme="jade", width="100%",
            ),
        ),
        spacing="2", align_items="start", width="100%",
    )


def _status() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AppState.export_busy,
            rx.hstack(
                rx.spinner(size="1"),
                rx.text(AppState.export_progress_label, size="1"),
                spacing="2", align="center", width="100%",
            ),
            rx.fragment(),
        ),
        rx.cond(
            AppState.export_error != "",
            rx.callout(AppState.export_error, icon="triangle-alert",
                       color_scheme="red", size="1", width="100%"),
            rx.fragment(),
        ),
        rx.cond(
            AppState.export_result != "",
            rx.callout(AppState.export_result, icon="circle-check",
                       color_scheme="jade", size="1", width="100%"),
            rx.fragment(),
        ),
        spacing="2", width="100%",
    )


def exportar_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("download", size=15),
                rx.text(AppState.tr["download_button"],
                       display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=AppState.tr["download_button"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(AppState.tr["export_dialog_title"]),
            rx.dialog.description(
                AppState.tr["export_dialog_desc"],
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.scroll_area(
                rx.vstack(
                    _study_point_section(),
                    rx.divider(),
                    _selection_section(),
                    rx.divider(),
                    _status(),
                    rx.callout(
                        AppState.tr["provenance_callout"],
                        icon="info", size="1", color_scheme="gray", width="100%",
                    ),
                    spacing="4", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "62vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                # A plain button driving export_open directly, not
                # rx.dialog.close — see components/help.py::como_usar_dialog for
                # why Dialog.Close's implicit prop-cloning silently fails here.
                rx.button(AppState.tr["close_button"], size="2", variant="soft",
                         on_click=AppState.set_export_open(False)),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "560px", "560px"],
        ),
        open=AppState.export_open,
        on_open_change=AppState.set_export_open,
    )
