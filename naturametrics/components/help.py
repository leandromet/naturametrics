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
    APP_URL, APP_YEAR, AUTHORS, BIBTEX, CITATION_TEXT, DATA_SOURCES,
)

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
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("circle-help", size=15),
                # Label collapses to an icon on phones — two labelled buttons do
                # not fit beside the wordmark at 390px and get clipped.
                rx.text("Como usar", display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label="Como usar",
            )
        ),
        rx.dialog.content(
            rx.dialog.title("Como usar o Naturametrics"),
            rx.dialog.description(
                "Análise da história de uso da terra e da paisagem em qualquer "
                "ponto do Brasil.",
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.scroll_area(
                rx.vstack(
                    _step("1", "Escolha um ponto",
                          "Clique em qualquer lugar do mapa. Um marcador é criado e "
                          "quatro áreas de análise (1, 2, 5 e 10 km de raio) são "
                          "desenhadas em volta dele. Cliques fora do Brasil são "
                          "recusados: o MapBiomas cobre apenas o território nacional."),
                    _step("2", "Leia a história de uso da terra",
                          "O gráfico abaixo do mapa traz uma coluna por ano, de 1985 a "
                          "2024, com as classes do MapBiomas nas cores oficiais. Troque "
                          "o raio em 1/2/5/10 km e use o botão «%» para alternar entre "
                          "hectares e proporção da área."),
                    _step("3", "Troque o mapa base",
                          "O padrão é o híbrido do Google, que traz nomes de "
                          "municípios e estradas — útil para conferir onde você "
                          "está. A lista inclui ainda o mosaico SPOT de 2008 do "
                          "Brasil, em cor natural e em falsa-cor infravermelha: "
                          "ele cobre só as áreas florestais do país, então há "
                          "vazios fora desse recorte, e fica desenhado por cima "
                          "do mapa base escolhido antes."),
                    _step("4", "Veja a cobertura no mapa",
                          "Ligue «MapBiomas 10.1» na barra lateral. O controle «Ano» "
                          "percorre 1985–2024 — todos os anos são pré-carregados, então "
                          "a troca é imediata e o mapa não sai do lugar. «Opacidade» "
                          "controla o quanto do mapa base aparece por baixo."),
                    _step("5", "Compare dois anos",
                          "«Cortina deslizante» mostra dois anos ao mesmo tempo, "
                          "separados por uma linha branca que você arrasta pelo mapa. O "
                          "ano da esquerda é escolhido no próprio painel; o da direita é "
                          "o ano selecionado em «Cobertura do solo». Cada lado tem sua "
                          "própria opacidade."),
                    _step("6", "Encontre candidatos a recuperação",
                          "«Mudança na vegetação natural» destaca em vermelho o que era "
                          "vegetação natural no ano base e deixou de ser, e em verde o "
                          "que regenerou. O padrão é 2008, marco do Código Florestal: "
                          "supressão posterior a 22/07/2008 tem obrigação de "
                          "recomposição."),
                    _step("7", "Trabalhe com os conglomerados do IFN",
                          "Ligue «Conglomerados» na barra lateral para ver os 17.479 "
                          "pontos do Inventário Florestal Nacional, e filtre por "
                          "região, bioma, estado e município — o mapa enquadra a "
                          "seleção sozinho. Aproximando o zoom, os pontos ficam "
                          "interativos: pare o cursor sobre um para ver a cobertura "
                          "num raio de 10 km hoje e em 1985 — e o próprio mapa mostra "
                          "o MapBiomas só dentro desse raio, no ano escolhido. Clique "
                          "para rodar a análise completa nas coordenadas oficiais "
                          "dele."),
                    _step("8", "Some vários conglomerados",
                          "Ligue «Seleção múltipla» na barra lateral e clique nos "
                          "conglomerados que interessam — clicar de novo remove — "
                          "ou segure Ctrl (Cmd no Mac) e arraste para pegar uma "
                          "área inteira de uma vez. "
                          "O gráfico passa a mostrar a soma das áreas de cada "
                          "raio em todos eles, e o mapa desenha os buffers de "
                          "todos ao mesmo tempo. Atenção: buffers que se "
                          "sobrepõem são contados uma vez em cada conglomerado, "
                          "então o total não é a área da união."),
                    _step("9", "Baixe os dados",
                          "Em «Baixar dados», no topo da página. São duas planilhas "
                          "ODS independentes: a do ponto de estudo atual, com uma aba "
                          "por raio e o pixel do próprio ponto ano a ano; e a da "
                          "seleção de conglomerados — pelos filtros do mapa ou "
                          "pelos pontos escolhidos à mão — onde você marca o que quer: "
                          "lista de pontos, classe do pixel ano a ano, e o histórico "
                          "dos buffers — com uma aba por raio, e a opção de exportar "
                          "um raio só, que faz caber muito mais conglomerados. Toda "
                          "planilha abre com uma aba «metadados» dizendo como cada "
                          "número foi calculado."),
                    rx.callout(
                        "Esta camada é uma triagem, não um laudo. Não considera CAR, "
                        "APP/Reserva Legal, porte do imóvel nem autorizações de "
                        "supressão. Use-a para orientar a investigação, não para "
                        "concluí-la.",
                        icon="triangle-alert", color_scheme="amber", size="1",
                        width="100%",
                    ),
                    rx.divider(),
                    rx.text("Limitações que valem conhecer", size="2", weight="bold"),
                    rx.unordered_list(
                        rx.list_item(
                            "Resolução de 30 m: num raio de 1 km cabem cerca de 3.500 "
                            "pixels, então poucos pixels mal classificados já mexem nas "
                            "porcentagens."
                        ),
                        rx.list_item(
                            "A série do MapBiomas começa em 1985 — não é possível saber "
                            "a idade de vegetação que já existia antes disso."
                        ),
                        rx.list_item(
                            "As áreas são calculadas com a área real do pixel "
                            "(ee.Image.pixelArea), que varia com a latitude; um valor "
                            "fixo de 0,09 ha superestimaria a área."
                        ),
                        rx.list_item(
                            "As classes do MapBiomas não são seguras para daltonismo — "
                            "a legenda sempre traz o nome ao lado da cor."
                        ),
                        font_size="var(--font-size-2)", color="var(--gray-11)",
                    ),
                    spacing="4", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "60vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                rx.dialog.close(rx.button("Fechar", size="2", variant="soft")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "640px", "640px"],
        ),
    )


def _source_row(name: str, detail: str, url: str) -> rx.Component:
    return rx.vstack(
        rx.link(name, href=url, is_external=True, size="2", weight="bold"),
        rx.text(detail, size="1", color_scheme="gray"),
        spacing="1", align_items="start", width="100%",
    )


def como_citar_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("quote", size=15),
                rx.text("Como citar", display=["none", "none", "block", "block"]),
                size="1", variant="soft", color_scheme="gray",
                aria_label="Como citar",
            )
        ),
        rx.dialog.content(
            rx.dialog.title("Como citar"),
            rx.dialog.description(
                "Se o Naturametrics contribuiu para o seu trabalho, cite-o e cite "
                "também as bases de dados utilizadas.",
                size="2", color_scheme="gray", margin_bottom="0.75rem",
            ),
            rx.scroll_area(
                rx.vstack(
                    rx.text("Citação sugerida", size="2", weight="bold"),
                    rx.box(
                        rx.text(CITATION_TEXT, size="2", style={"lineHeight": "1.6"}),
                        padding="0.75rem", background="var(--gray-3)",
                        border_radius="6px", width="100%",
                    ),
                    rx.button(
                        rx.icon("copy", size=13), "Copiar citação",
                        on_click=rx.set_clipboard(CITATION_TEXT),
                        size="1", variant="soft", color_scheme="jade",
                    ),

                    rx.divider(),
                    rx.text("BibTeX", size="2", weight="bold"),
                    rx.code_block(BIBTEX, language="latex", show_line_numbers=False,
                                  wrap_long_lines=True, font_size="0.75rem"),
                    rx.button(
                        rx.icon("copy", size=13), "Copiar BibTeX",
                        on_click=rx.set_clipboard(BIBTEX),
                        size="1", variant="soft", color_scheme="jade",
                    ),

                    rx.divider(),
                    rx.text("Autores e instituições", size="2", weight="bold"),
                    rx.vstack(
                        *[
                            rx.vstack(
                                rx.text(name, size="2", weight="medium"),
                                rx.text(inst, size="1", color_scheme="gray"),
                                spacing="0", align_items="start",
                            )
                            for name, inst in AUTHORS
                        ],
                        spacing="3", align_items="start", width="100%",
                    ),

                    rx.divider(),
                    rx.text("Bases de dados — cite também", size="2", weight="bold"),
                    rx.text(
                        "Cada base tem exigências próprias de atribuição. Ao publicar "
                        "figuras ou números obtidos aqui, cite as que foram usadas.",
                        size="1", color_scheme="gray",
                    ),
                    rx.vstack(
                        *[_source_row(n, d, u) for n, d, u in DATA_SOURCES],
                        spacing="3", align_items="start", width="100%",
                    ),

                    rx.divider(),
                    rx.callout(
                        "As imagens SPOT 2008 (Brazil Forest Imagery Dataset) exigem "
                        "aceite de licença específica do Google e ainda não estão "
                        "habilitadas nesta instância.",
                        icon="info", color_scheme="gray", size="1", width="100%",
                    ),
                    spacing="3", align_items="start", width="100%",
                ),
                type="auto", scrollbars="vertical",
                style={"maxHeight": "60vh", "paddingRight": "1rem"},
            ),
            rx.flex(
                rx.dialog.close(rx.button("Fechar", size="2", variant="soft")),
                justify="end", margin_top="1rem",
            ),
            max_width=["94vw", "94vw", "660px", "660px"],
        ),
    )


def header_actions() -> rx.Component:
    from .exports import exportar_dialog

    # Imported inside the function: components/exports.py imports the state, and
    # the state imports components/charts.py. At module scope that closes into a
    # circular import; here the cycle is resolved by the time the page is built.
    return rx.hstack(exportar_dialog(), como_usar_dialog(), como_citar_dialog(),
                     spacing="2")
