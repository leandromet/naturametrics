"""Header panels: "Como usar" and "Como citar".

Two Radix dialogs rather than Yvynation's hand-rolled overlay-plus-state-toggle:
`rx.dialog` brings focus trapping, Escape-to-close and the backdrop for free, and
needs no state var of its own.

The citation panel also discharges constraint **C4** (doc/01-premises.md): every
dataset the app draws must carry its required attribution somewhere the user can
find it.
"""

from __future__ import annotations

import reflex as rx

from ..config.citation import (
    APP_URL, APP_YEAR, AUTHORS, AUTHORS_EN, BIBTEX, CITATION_TEXT,
    DATA_SOURCES, DATA_SOURCES_EN,
)
from ..state import AppState

def _step(number: str, title: str, body: str) -> rx.Component:
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


def como_usar_dialog() -> rx.Component:
    tr = AppState.tr
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("circle-help", size=15),
                # Label collapses to an icon on phones — two labelled buttons do
                # not fit beside the wordmark at 390px and get clipped.
                rx.text(tr["help_trigger"], display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=tr["help_trigger"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(tr["help_dialog_title"]),
            rx.dialog.description(
                tr["help_dialog_desc"],
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.scroll_area(
                rx.vstack(
                    _step("1", tr["help_step1_title"], tr["help_step1_body"]),
                    _step("2", tr["help_step2_title"], tr["help_step2_body"]),
                    _step("3", tr["help_step3_title"], tr["help_step3_body"]),
                    _step("4", tr["help_step4_title"], tr["help_step4_body"]),
                    _step("5", tr["help_step5_title"], tr["help_step5_body"]),
                    _step("6", tr["help_step6_title"], tr["help_step6_body"]),
                    _step("7", tr["help_step7_title"], tr["help_step7_body"]),
                    _step("8", tr["help_step8_title"], tr["help_step8_body"]),
                    _step("9", tr["help_step9_title"], tr["help_step9_body"]),
                    rx.callout(
                        tr["help_triage_callout"],
                        icon="triangle-alert", color_scheme="amber", size="1",
                        width="100%",
                    ),
                    rx.divider(),
                    rx.text(tr["help_limitations_title"], size="2", weight="bold"),
                    rx.unordered_list(
                        rx.list_item(tr["help_limit_1"]),
                        rx.list_item(tr["help_limit_2"]),
                        rx.list_item(tr["help_limit_3"]),
                        rx.list_item(tr["help_limit_4"]),
                        font_size="var(--font-size-2)", color="var(--gray-11)",
                    ),
                    spacing="4", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "60vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                # Reflex deduplicates byte-identical rx.button(...) subtrees into
                # one shared, prop-less helper component. Dialog.Close relies on
                # Radix's asChild cloning to inject its onClick/ref onto this
                # button at runtime, and a deduped helper — since it takes no
                # props — silently drops that injection: the button renders but
                # clicking it does nothing (only Escape still closes the dialog,
                # via a separate document-level listener). A distinguishing id
                # is enough to keep this button's subtree unique per dialog, so
                # Reflex compiles it inline instead of extracting it.
                rx.dialog.close(rx.button(tr["close_button"], size="2",
                                          variant="soft", id="dialog-close-como-usar")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "640px", "640px"],
        ),
    )


def _source_row(name_pt: str, name_en: str, detail_pt: str, detail_en: str,
                url: str) -> rx.Component:
    return rx.vstack(
        rx.link(rx.cond(AppState.language == "pt", name_pt, name_en),
               href=url, is_external=True, size="2", weight="bold"),
        rx.text(rx.cond(AppState.language == "pt", detail_pt, detail_en),
               size="1", color_scheme="gray"),
        spacing="1", align_items="start", width="100%",
    )


def como_citar_dialog() -> rx.Component:
    tr = AppState.tr
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("quote", size=15),
                rx.text(tr["cite_trigger"], display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=tr["cite_trigger"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(tr["cite_dialog_title"]),
            rx.dialog.description(
                tr["cite_dialog_desc"],
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.scroll_area(
                rx.vstack(
                    # The citation string and BibTeX entry are the canonical,
                    # copy-pasteable reference — they stay exactly as published
                    # regardless of UI language, the same way a DOI record does.
                    rx.text(tr["cite_suggested_title"], size="2", weight="bold"),
                    rx.box(
                        rx.text(CITATION_TEXT, size="2", style={"lineHeight": "1.6"}),
                        padding="0.75rem", background="var(--gray-3)",
                        border_radius="6px", width="100%",
                    ),
                    rx.button(
                        rx.icon("copy", size=13), tr["cite_copy_citation"],
                        on_click=rx.set_clipboard(CITATION_TEXT),
                        size="1", variant="soft", color_scheme="jade",
                    ),

                    rx.divider(),
                    rx.text(tr["cite_bibtex_title"], size="2", weight="bold"),
                    rx.code_block(BIBTEX, language="latex", show_line_numbers=False,
                                  wrap_long_lines=True, font_size="0.75rem"),
                    rx.button(
                        rx.icon("copy", size=13), tr["cite_copy_bibtex"],
                        on_click=rx.set_clipboard(BIBTEX),
                        size="1", variant="soft", color_scheme="jade",
                    ),

                    rx.divider(),
                    rx.text(tr["cite_authors_title"], size="2", weight="bold"),
                    rx.vstack(
                        *[
                            rx.vstack(
                                rx.text(name, size="2", weight="medium"),
                                rx.text(
                                    rx.cond(AppState.language == "pt", inst_pt, inst_en),
                                    size="1", color_scheme="gray",
                                ),
                                spacing="0", align_items="start",
                            )
                            for (name, inst_pt), (_, inst_en)
                            in zip(AUTHORS, AUTHORS_EN)
                        ],
                        spacing="3", align_items="start", width="100%",
                    ),

                    rx.divider(),
                    rx.text(tr["cite_sources_title"], size="2", weight="bold"),
                    rx.text(tr["cite_sources_desc"], size="1", color_scheme="gray"),
                    rx.vstack(
                        *[
                            _source_row(n_pt, n_en, d_pt, d_en, u)
                            for (n_pt, d_pt, u), (n_en, d_en, _)
                            in zip(DATA_SOURCES, DATA_SOURCES_EN)
                        ],
                        spacing="3", align_items="start", width="100%",
                    ),

                    rx.divider(),
                    rx.callout(
                        tr["cite_spot_callout"],
                        icon="info", color_scheme="gray", size="1", width="100%",
                    ),
                    spacing="3", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "60vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                # Unique id — see como_usar_dialog above for why this matters.
                rx.dialog.close(rx.button(tr["close_button"], size="2",
                                          variant="soft", id="dialog-close-como-citar")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "660px", "660px"],
        ),
    )


def ai_disclaimer_dialog() -> rx.Component:
    tr = AppState.tr
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("sparkles", size=15),
                rx.text(tr["ai_trigger"],
                       display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label=tr["ai_trigger"],
            )
        ),
        rx.dialog.content(
            rx.dialog.title(tr["ai_trigger"]),
            rx.dialog.description(
                tr["ai_dialog_desc"],
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.vstack(
                rx.text(
                    tr["ai_para1"],
                    size="2", style={"lineHeight": "1.6"},
                ),
                rx.text(
                    tr["ai_para2"],
                    size="2", color_scheme="gray", style={"lineHeight": "1.6"},
                ),
                rx.divider(),
                rx.text(tr["ai_see_yourself_title"], size="2", weight="bold"),
                rx.vstack(
                    rx.link(tr["ai_yvynation_link"],
                           href="https://yvynation-reflex-652582010777.us-west1.run.app/",
                           is_external=True, size="2", weight="medium"),
                    rx.link("github.com/leandromet/naturametrics",
                           href="https://github.com/leandromet/naturametrics",
                           is_external=True, size="2", weight="medium"),
                    rx.link("github.com/leandromet/yvynation",
                           href="https://github.com/leandromet/yvynation",
                           is_external=True, size="2", weight="medium"),
                    spacing="2", align_items="start", width="100%",
                ),
                spacing="3", align_items="start", width="100%",
            ),
            rx.flex(
                rx.dialog.close(rx.button(tr["close_button"], size="2", variant="soft")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "560px", "560px"],
        ),
    )


def header_actions() -> rx.Component:
    from .exports import exportar_dialog

    # Imported inside the function: components/exports.py imports the state, and
    # the state imports components/charts.py. At module scope that closes into a
    # circular import; here the cycle is resolved by the time the page is built.
    return rx.hstack(exportar_dialog(), como_usar_dialog(), como_citar_dialog(),
                     ai_disclaimer_dialog(), spacing="2")
