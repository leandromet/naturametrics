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

from ..config.settings import BUFFER_RADII_KM, EXPORT_BUFFER_MAX_POINTS
from ..state import AppState

_RADII = ", ".join(f"{r:g}" for r in sorted(BUFFER_RADII_KM))


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
            rx.text("Ponto de estudo", size="2", weight="bold"),
            rx.spacer(),
            rx.cond(
                AppState.has_result,
                rx.badge(AppState.point_label, size="1", variant="soft",
                         color_scheme="jade"),
                rx.badge("nenhum ponto", size="1", variant="soft",
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
            f"Uma planilha com: o pixel do próprio ponto ano a ano, uma aba por "
            f"raio ({_RADII} km) com a série completa 1985–2024, um resumo de "
            f"variação por classe, o dicionário de classes do MapBiomas e a aba "
            f"de metadados com a proveniência de cada consulta.",
            size="1", color_scheme="gray", style={"lineHeight": "1.45"},
        ),
        rx.button(
            rx.icon("download", size=14),
            "Baixar planilha do ponto (.ods)",
            on_click=AppState.download_study_point,
            disabled=~AppState.has_result | AppState.export_busy,
            size="2", color_scheme="jade", width="100%",
        ),
        rx.cond(
            AppState.has_result,
            rx.fragment(),
            rx.text("Clique num ponto ou num conglomerado do mapa para habilitar.",
                    size="1", color_scheme="gray"),
        ),
        spacing="2", align_items="start", width="100%",
    )


def _selection_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("Seleção de conglomerados", size="2", weight="bold"),
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
            "Sai ponto a ponto, um conglomerado por linha — a soma que aparece "
            "no gráfico é uma leitura, não o formato do arquivo.",
            size="1", color_scheme="gray",
        ),
        rx.divider(),
        _check(
            "Lista de conglomerados",
            "Um por linha: identificador, região, UF, município, bioma e "
            "coordenadas. Instantâneo.",
            AppState.exp_points, AppState.toggle_exp_points,
        ),
        _check(
            "Classe do pixel, ano a ano",
            "O pixel de 30 m de cada conglomerado, uma coluna por ano de 1985 a "
            "2024. Sem limite de tamanho — a seleção inteira sai em segundos.",
            AppState.exp_pixel, AppState.toggle_exp_pixel,
        ),
        _check(
            f"Histórico dos buffers de {_RADII} km",
            f"Área por classe, por ano e por raio, para cada conglomerado — a "
            f"mesma conta que o gráfico faz. É a parte cara: limite de "
            f"{EXPORT_BUFFER_MAX_POINTS} conglomerados.".replace(",", "."),
            AppState.exp_buffers, AppState.toggle_exp_buffers,
            disabled=~AppState.export_buffers_allowed,
        ),
        rx.cond(
            AppState.exp_buffers | ~AppState.export_buffers_allowed,
            rx.callout(
                AppState.export_buffer_note,
                icon="clock",
                size="1",
                color_scheme=rx.cond(AppState.export_buffers_allowed,
                                     "gray", "amber"),
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.button(
            rx.icon("download", size=14),
            "Baixar planilha da seleção (.ods)",
            on_click=AppState.download_selection,
            disabled=AppState.export_busy | AppState.export_nothing_selected
                     | (AppState.export_selection_count == 0),
            size="2", color_scheme="jade", width="100%",
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
                rx.text("Baixar dados", display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label="Baixar dados",
            )
        ),
        rx.dialog.content(
            rx.dialog.title("Baixar dados"),
            rx.dialog.description(
                "Cada download é uma planilha ODS com uma aba por tabela e uma "
                "aba de metadados com a proveniência completa. Abre no "
                "LibreOffice, no Excel e no Google Planilhas.",
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
                        "Nenhum número sai daqui sem proveniência: a aba "
                        "«metadados» diz qual coleção, quais bandas, qual escala "
                        "e qual redutor produziram cada tabela, e traz as "
                        "atribuições que devem ser citadas.",
                        icon="info", size="1", color_scheme="gray", width="100%",
                    ),
                    spacing="4", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "62vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                rx.dialog.close(rx.button("Fechar", size="2", variant="soft")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "560px", "560px"],
        ),
        open=AppState.export_open,
        on_open_change=AppState.set_export_open,
    )
