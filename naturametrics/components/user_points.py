""""Enviar dados": three ways to hand the app a study area without clicking
the map — a pasted coordinate list standing in for the IFN grid, a pasted WKT
polygon, or an uploaded KML file. The first produces points
(state/_user_points.py); the other two produce a single region
(state/_geometry.py) — see that module and services/region_geometry.py for why
KML upload specifically was worth reopening the safety surface the coordinate
list deliberately avoids.

The dialog mirrors exportar_dialog()'s shape (trigger, scrollable content, a
status area) so the two "open a panel from the header" flows in this app feel
like the same feature rather than two different ones.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState


def _error_row(msg: rx.Var) -> rx.Component:
    return rx.text(f"· {msg}", size="1", color_scheme="amber",
                   style={"lineHeight": "1.4"})


def _points_tab() -> rx.Component:
    return rx.vstack(
        rx.text(AppState.tr["send_format_label"], size="1", weight="medium"),
        rx.code_block(
            AppState.user_points_example,
            language="markup", can_copy=True, size="1",
            width="100%",
        ),
        rx.text_area(
            placeholder=AppState.user_points_example,
            value=AppState.user_points_text,
            on_change=AppState.set_user_points_text,
            rows="8", size="2", width="100%",
            style={"fontFamily": "monospace"},
        ),
        rx.hstack(
            rx.text(
                AppState.user_points_max_label,
                size="1", color_scheme="gray",
            ),
            rx.spacer(),
            rx.cond(
                AppState.user_points_active,
                rx.badge(AppState.user_points_active_label,
                         size="1", variant="soft", color_scheme="jade"),
                rx.fragment(),
            ),
            width="100%", align="center",
        ),
        rx.cond(
            AppState.user_points_has_errors,
            rx.vstack(
                rx.foreach(AppState.user_points_errors, _error_row),
                spacing="1", width="100%",
                style={"maxHeight": "140px", "overflowY": "auto"},
            ),
            rx.fragment(),
        ),
        rx.hstack(
            rx.button(
                rx.icon("upload", size=14),
                AppState.tr["submit_button"],
                on_click=AppState.submit_user_points,
                disabled=AppState.user_points_text == "",
                size="2", color_scheme="jade",
            ),
            rx.cond(
                AppState.user_points_active,
                rx.button(
                    rx.icon("rotate-ccw", size=14),
                    AppState.tr["reset_button"],
                    on_click=AppState.reset_user_points,
                    size="2", variant="soft", color_scheme="gray",
                ),
                rx.fragment(),
            ),
            spacing="2",
        ),
        spacing="3", align_items="start", width="100%",
    )


def _wkt_tab() -> rx.Component:
    return rx.vstack(
        rx.text(AppState.tr["send_wkt_desc"], size="1", color_scheme="gray",
                style={"lineHeight": "1.4"}),
        rx.text_area(
            placeholder=AppState.tr["send_wkt_placeholder"],
            value=AppState.wkt_text,
            on_change=AppState.set_wkt_text,
            rows="8", size="2", width="100%",
            style={"fontFamily": "monospace"},
        ),
        rx.cond(
            AppState.geometry_error != "",
            _error_row(AppState.geometry_error),
            rx.fragment(),
        ),
        rx.button(
            rx.icon("upload", size=14),
            AppState.tr["submit_button"],
            on_click=AppState.submit_wkt,
            disabled=AppState.wkt_text == "",
            size="2", color_scheme="jade",
        ),
        spacing="3", align_items="start", width="100%",
    )


def _kml_tab() -> rx.Component:
    return rx.vstack(
        rx.text(AppState.tr["send_kml_desc"], size="1", color_scheme="gray",
                style={"lineHeight": "1.4"}),
        rx.upload.root(
            rx.vstack(
                rx.icon("upload", size=18, color="var(--gray-9)"),
                rx.text(AppState.tr["send_kml_dropzone"], size="1",
                        color_scheme="gray", text_align="center"),
                spacing="1", align="center",
            ),
            id="nm_kml_upload",
            accept={"application/vnd.google-earth.kml+xml": [".kml"]},
            max_files=1,
            multiple=False,
            on_drop=AppState.handle_kml_upload(
                rx.upload_files(upload_id="nm_kml_upload")),
            border="1px dashed var(--gray-7)",
            border_radius="6px",
            padding="1.5rem",
            width="100%",
            cursor="pointer",
        ),
        rx.cond(
            AppState.geometry_error != "",
            _error_row(AppState.geometry_error),
            rx.fragment(),
        ),
        spacing="3", align_items="stretch", width="100%",
    )


def enviar_dados_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("clipboard-list", size=15),
                rx.text(AppState.tr["send_button"],
                       display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=AppState.tr["send_list_aria"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(AppState.tr["send_dialog_title"]),
            rx.dialog.description(
                AppState.tr["send_dialog_desc"],
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.vstack(
                rx.segmented_control.root(
                    rx.segmented_control.item(
                        AppState.tr["send_mode_points"], value="points"),
                    rx.segmented_control.item(
                        AppState.tr["send_mode_wkt"], value="wkt"),
                    rx.segmented_control.item(
                        AppState.tr["send_mode_kml"], value="kml"),
                    value=AppState.send_data_mode,
                    on_change=AppState.set_send_data_mode,
                    size="1", width="100%",
                ),
                rx.match(
                    AppState.send_data_mode,
                    ("wkt", _wkt_tab()),
                    ("kml", _kml_tab()),
                    _points_tab(),
                ),
                spacing="3", align_items="start", width="100%",
            ),
            rx.flex(
                # A plain button driving state directly, not rx.dialog.close —
                # see components/help.py::como_usar_dialog for why.
                rx.button(AppState.tr["close_button"], size="2", variant="soft",
                         on_click=AppState.set_user_points_dialog_open(False)),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "560px", "560px"],
        ),
        open=AppState.user_points_dialog_open,
        on_open_change=AppState.set_user_points_dialog_open,
    )
