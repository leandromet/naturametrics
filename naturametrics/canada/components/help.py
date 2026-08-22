"""Header dialogs for the Canada page: how to use, how to cite, and downloads."""

from __future__ import annotations

import reflex as rx

from ...config.citation import DATA_SOURCES, DATA_SOURCES_EN
from ...config.settings import BUFFER_RADII_KM
from ..state import CanadaState as S
from ..translations import get_translations

_RADII = ", ".join(f"{r:g}" for r in sorted(BUFFER_RADII_KM))


def _tr_radii(key: str) -> rx.Var:
    """A translated string with ``{radii}`` filled in at build time.

    ``S.tr[key]`` is a runtime Var and Python's ``.format()`` cannot run on it in
    the component tree. ``_RADII`` never changes, so both language variants are
    formatted once here and switched with ``rx.cond`` — same approach as the
    Brazil export panel.
    """
    return rx.cond(
        S.language == "pt",
        get_translations("pt")[key].format(radii=_RADII),
        get_translations("en")[key].format(radii=_RADII),
    )


def _step(number: str, title, body) -> rx.Component:
    return rx.hstack(
        rx.badge(number, color_scheme="jade", variant="solid", size="1",
                 style={"minWidth": "22px", "justifyContent": "center"}),
        rx.vstack(
            rx.text(title, size="2", weight="bold"),
            rx.text(body, size="2", color_scheme="gray"),
            spacing="1", align_items="start",
        ),
        spacing="3", align_items="start", width="100%",
    )


def how_to_use_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("circle-help", size=15),
                rx.text(S.tr["help_trigger"],
                        display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=S.tr["help_trigger"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(S.tr["help_dialog_title"]),
            rx.dialog.description(S.tr["help_dialog_desc"], size="2",
                                  color_scheme="gray", margin_bottom="0.75rem"),
            rx.scroll_area(
                rx.vstack(
                    _step("1", S.tr["help_step1_title"], S.tr["help_step1_body"]),
                    _step("2", S.tr["help_step2_title"], S.tr["help_step2_body"]),
                    _step("3", S.tr["help_step3_title"], S.tr["help_step3_body"]),
                    _step("4", S.tr["help_step4_title"], S.tr["help_step4_body"]),
                    _step("5", S.tr["help_step5_title"], S.tr["help_step5_body"]),
                    _step("6", S.tr["help_step6_title"], S.tr["help_step6_body"]),
                    _step("7", S.tr["help_step7_title"], S.tr["help_step7_body"]),
                    rx.divider(),
                    rx.text(S.tr["help_limitations_title"], size="2", weight="bold"),
                    rx.unordered_list(
                        rx.list_item(S.tr["help_limit_1"]),
                        rx.list_item(S.tr["help_limit_2"]),
                        rx.list_item(S.tr["help_limit_3"]),
                        rx.list_item(S.tr["help_limit_4"]),
                        font_size="var(--font-size-2)", color="var(--gray-11)",
                    ),
                    spacing="4", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "60vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                # A plain button driving state directly, not rx.dialog.close:
                # any button used solely as Dialog.Close's child gets compiled
                # by Reflex into its own standalone helper component that takes
                # no props, so the onClick/ref Radix's "asChild" cloning tries
                # to inject onto it at runtime never arrives. See
                # naturametrics/components/help.py::como_usar_dialog for the trace.
                rx.button(S.tr["close_button"], size="2", variant="soft",
                         on_click=S.set_help_open(False)),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "640px", "640px"],
        ),
        open=S.help_open,
        on_open_change=S.set_help_open,
    )


def _source_row(name_pt: str, name_en: str, detail_pt: str, detail_en: str,
                url: str) -> rx.Component:
    """Bilingual, mirroring the Brazil page's cite dialog — see
    ``naturametrics/components/help.py::_source_row``. The two pages share one
    source list (``config/citation.py``), so this needs the same shape."""
    return rx.vstack(
        rx.link(rx.cond(S.language == "pt", name_pt, name_en),
               href=url, is_external=True, size="2", weight="bold"),
        rx.text(rx.cond(S.language == "pt", detail_pt, detail_en),
               size="1", color_scheme="gray"),
        spacing="1", align_items="start", width="100%",
    )


def how_to_cite_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("quote", size=15),
                rx.text(S.tr["cite_trigger"],
                        display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=S.tr["cite_trigger"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(S.tr["cite_dialog_title"]),
            rx.dialog.description(S.tr["cite_dialog_desc"], size="2",
                                  color_scheme="gray", margin_bottom="0.75rem"),
            rx.scroll_area(
                rx.vstack(
                    rx.text(S.tr["cite_sources_title"], size="2", weight="bold"),
                    rx.text(S.tr["cite_sources_desc"], size="1", color_scheme="gray"),
                    rx.vstack(
                        *[
                            _source_row(n_pt, n_en, d_pt, d_en, u)
                            for (n_pt, d_pt, u), (n_en, d_en, _)
                            in zip(DATA_SOURCES, DATA_SOURCES_EN)
                        ],
                        spacing="3", align_items="start", width="100%",
                    ),
                    rx.divider(),
                    rx.text(S.tr["cite_example_title"], size="2", weight="bold"),
                    rx.box(
                        rx.text(S.tr["cite_example_body"], size="2",
                               style={"lineHeight": "1.6", "fontStyle": "italic"}),
                        padding="0.75rem", background="var(--gray-3)",
                        border_radius="6px", width="100%",
                    ),
                    spacing="3", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "60vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                # Plain button + state — see how_to_use_dialog above for why.
                rx.button(S.tr["close_button"], size="2", variant="soft",
                         on_click=S.set_cite_open(False)),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "620px", "620px"],
        ),
        open=S.cite_open,
        on_open_change=S.set_cite_open,
    )


def export_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("download", size=15),
                rx.text(S.tr["download_button"],
                        display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=S.tr["download_button"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(S.tr["export_dialog_title"]),
            rx.dialog.description(S.tr["export_dialog_desc"], size="2",
                                  color_scheme="gray", margin_bottom="0.75rem"),
            rx.vstack(
                rx.hstack(
                    rx.text(S.tr["section_point"], size="2", weight="bold"),
                    rx.spacer(),
                    rx.cond(
                        S.has_result,
                        rx.badge(S.point_label, size="1", variant="soft",
                                 color_scheme="jade"),
                        rx.badge(S.tr["no_point_badge"], size="1", variant="soft",
                                 color_scheme="gray"),
                    ),
                    width="100%", align="center",
                ),
                rx.text(_tr_radii("export_point_desc"), size="1",
                        color_scheme="gray", style={"lineHeight": "1.45"}),
                rx.button(
                    rx.icon("download", size=14),
                    S.tr["download_point_button"],
                    on_click=S.download_study_point,
                    disabled=~S.has_result | S.export_busy,
                    size="2", color_scheme="jade", width="100%",
                ),
                rx.cond(
                    S.has_result,
                    rx.fragment(),
                    rx.text(S.tr["download_point_hint"], size="1",
                            color_scheme="gray"),
                ),
                rx.cond(
                    S.export_busy,
                    rx.hstack(rx.spinner(size="1"),
                              rx.text(S.tr["export_stage_building"], size="1"),
                              spacing="2", align="center", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    S.export_error != "",
                    rx.callout(S.export_error, icon="triangle-alert",
                               color_scheme="red", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.cond(
                    S.export_result != "",
                    rx.callout(S.export_result, icon="circle-check",
                               color_scheme="jade", size="1", width="100%"),
                    rx.fragment(),
                ),
                rx.callout(S.tr["provenance_callout"], icon="info", size="1",
                           color_scheme="gray", width="100%"),
                spacing="3", align_items="start", width="100%",
            ),
            rx.flex(
                # A plain button driving export_open directly, not
                # rx.dialog.close — see how_to_use_dialog above for why.
                rx.button(S.tr["close_button"], size="2", variant="soft",
                         on_click=S.set_export_open(False)),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "560px", "560px"],
        ),
        open=S.export_open,
        on_open_change=S.set_export_open,
    )


def header_actions() -> rx.Component:
    return rx.hstack(export_dialog(), how_to_use_dialog(), how_to_cite_dialog(),
                     spacing="2")
