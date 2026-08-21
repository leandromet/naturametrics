""""Enviar dados": a pasted coordinate list standing in for the IFN grid.

Paste-only, no file input — see services/user_points.py for why. The dialog
mirrors exportar_dialog()'s shape (trigger, scrollable content, a status area)
so the two "open a panel from the header" flows in this app feel like the same
feature rather than two different ones.
"""

from __future__ import annotations

import reflex as rx

from ..state import AppState


def _error_row(msg: rx.Var) -> rx.Component:
    return rx.text(f"· {msg}", size="1", color_scheme="amber",
                   style={"lineHeight": "1.4"})


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
                rx.text(AppState.tr["send_format_label"],
                        size="1", weight="medium"),
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
            ),
            rx.flex(
                rx.dialog.close(rx.button(AppState.tr["close_button"], size="2",
                                          variant="soft")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "560px", "560px"],
        ),
        open=AppState.user_points_dialog_open,
        on_open_change=AppState.set_user_points_dialog_open,
    )
