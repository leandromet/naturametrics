"""Portuguese overrides for the Canada page. Missing keys fall back to English."""

from __future__ import annotations

TRANSLATIONS_PT: dict[str, str] = {
    # --- header / drawer ------------------------------------------------- #
    "nav_toggle_layers_aria": "Abrir painel de camadas",
    "nav_subtitle": "Inventário agrícola, idade e mudança da floresta",
    "nav_title_suffix": "Canadá",
    "drawer_title": "Camadas e análise",
    "drawer_close_aria": "Fechar painel",
    "go_to_brazil": "Ir para o Brasil",
    "language_label": "Idioma",
    "close_button": "Fechar",
    "clear_button": "Limpar",
    "reset_button": "Resetar",
    "cancel_button": "Cancelar",

    # --- layer panel: sections -------------------------------------------- #
    "section_point": "Ponto de estudo",
    "section_basemap": "Mapa base",
    "section_landcover": "Inventário agrícola (AAFC)",
    "section_buffer_preview": "Uso no buffer",
    "buffer_preview_toggle_label": "Ampliar invent\u00e1rio agr\u00edcola",
    "buffer_preview_text": (
        "Mostra o invent\u00e1rio agr\u00edcola mais recente ({year}) apenas dentro do "
        "raio de an\u00e1lise em volta do ponto clicado, e em nenhum outro lugar. "
        "N\u00e3o consulta o Earth Engine: os blocos j\u00e1 est\u00e3o carregados e o "
        "c\u00edrculo \u00e9 um recorte aplicado no navegador."
    ),
    "buffer_preview_hidden_note": (
        "Redundante enquanto a camada completa do invent\u00e1rio est\u00e1 ligada "
        "\u2014 a cobertura j\u00e1 aparece no mapa inteiro."
    ),
    "section_forest_age": "Idade da floresta (NTEMS)",
    "section_forest_change": "Mudança florestal (Hansen)",
    "section_landsat": "Imagens Landsat",

    "year_label": "Ano",
    "opacity_label": "Opacidade",
    "aci_toggle_label": "Inventário Anual de Culturas",
    "aci_coverage_note": (
        "O Inventário Anual de Culturas é um produto agrícola: cobre o sul "
        "povoado e termina por volta de 58°N. A cobertura nacional começa em "
        "2011 — 2009 e 2010 abrangem apenas as Pradarias."
    ),
    "aci_north_warning": (
        "Este ponto está ao norte do limite do inventário agrícola, então o "
        "gráfico de cobertura não tem o que mostrar. A idade e a mudança da "
        "floresta cobrem todo o Canadá e não são afetadas."
    ),

    "forest_age_toggle_label": "Idade do povoamento",
    "forest_age_note": (
        "Idade medida do povoamento pelo NTEMS, referente a 2019 — não "
        "derivada de série temporal. Só pixels florestais têm valor; o resto "
        "fica transparente, o que é o dado dizendo «não é floresta», e não "
        "«sem dado»."
    ),

    "forest_change_toggle_label": "Perda e ganho",
    "change_base_year": "Perda a partir de",
    "change_loss_label": "Perda de cobertura arbórea",
    "change_gain_label": "Ganho de cobertura arbórea",
    "treecover_threshold_label": "Limiar de floresta (% de dossel em 2000)",
    "forest_change_note": (
        "Hansen Global Forest Change, 2001–2025. O controle de ano filtra "
        "apenas a perda: o ganho é publicado como um único indicador sem data "
        "para todo o período, então o verde não muda ao mover o controle."
    ),
    "hansen_treecover_toggle": "Cobertura arbórea 2000",

    "landsat_year_label": "Ano do composto",
    "landsat_note": (
        "Um composto Landsat sem nuvens por ano, de 1984 a 2026. Desenhado "
        "sobre o mapa base escolhido acima."
    ),

    "point_click_other": "Clique no mapa para escolher outro ponto.",
    "point_click_choose": "Clique no mapa para escolher um ponto.",

    "status_ee_unavailable": "Earth Engine indisponível",
    "status_ee_connecting": "Conectando ao Earth Engine…",
    "status_ee_ready": "Earth Engine pronto",

    # --- results ------------------------------------------------------------ #
    "landuse_title": "História do inventário agrícola",
    "analysis_running": "Reduzindo 17 anos sobre 4 buffers…",
    "top_classes_title": "Classes principais ({year})",
    "empty_state_title": "Clique no mapa para escolher um ponto",
    "empty_state_body": (
        "A história do inventário agrícola (2009–2025), a idade da floresta e "
        "a mudança florestal de Hansen serão calculadas para raios de 1, 2, 5 "
        "e 10 km em volta dele."
    ),
    "aci_empty_title": "Sem dados do inventário agrícola aqui",
    "forest_age_title": "Idade da floresta",
    "age_running": "Lendo o raster de idade do NTEMS…",
    "age_median_label": "Faixa de idade mediana",
    "age_forest_area_label": "Área florestal",
    "age_forest_pct_label": "Parcela do buffer que é floresta",
    "age_reference_note": "As idades são referentes a {year}, ano de referência do NTEMS.",
    "age_point_label": "Idade no pixel clicado",
    "age_point_not_forest": "O pixel clicado não é floresta",
    "age_years_unit": "anos",
    "change_title": "Mudança florestal {first}–{last}",
    "change_loss_ha": "Perda 2001\u20132025",
    "change_gain_ha": "Ganho 2000\u20132012",
    "change_net_ha": "Saldo 2001\u20132012",
    "change_gain_undated_note": (
        "O Hansen data a perda ano a ano, mas o ganho \u00e9 um indicador sem data "
        "que cobre apenas 2000\u20132012 e \u201cn\u00e3o foi atualizado nas vers\u00f5es "
        "seguintes\u201d. Por isso o ganho \u00e9 a linha tracejada dentro da faixa "
        "sombreada, e n\u00e3o uma s\u00e9rie, e o saldo \u00e9 de 2001\u20132012 \u2014 os anos que "
        "as duas bandas compartilham."
    ),
    "change_forest2000_ha": "Floresta em 2000",
    "change_running": "Lendo perda e ganho do Hansen…",
    "radius_label": "Raio",

    # --- export ------------------------------------------------------------- #
    "download_button": "Baixar dados",
    "export_dialog_title": "Baixar dados",
    "export_dialog_desc": (
        "Uma planilha ODS com uma aba por tabela e uma aba de metadados com a "
        "proveniência completa de cada consulta. Abre no LibreOffice, no Excel "
        "e no Google Planilhas."
    ),
    "export_point_desc": (
        "Uma planilha com: a classe do inventário agrícola no pixel clicado ano "
        "a ano, uma aba por raio ({radii} km) com a série completa 2009–2025, o "
        "histograma de idade da floresta, perda/ganho do Hansen, o dicionário "
        "de classes AAFC e a aba de metadados."
    ),
    "download_point_button": "Baixar planilha do ponto (.ods)",
    "download_point_hint": "Clique num ponto do mapa para habilitar.",
    "export_choose_point_first": "Escolha um ponto no mapa primeiro.",
    "export_stage_building": "Montando a planilha",
    "export_sheet_failed": "Falha ao gerar a planilha: {exc}",
    "provenance_callout": (
        "Nenhum número sai daqui sem proveniência: a aba de metadados diz qual "
        "conjunto de dados, quais bandas, qual escala e qual redutor "
        "produziram cada tabela, e traz as atribuições que devem ser citadas."
    ),
    "no_point_badge": "nenhum ponto",

    # --- errors -------------------------------------------------------------- #
    "err_coord_swapped": (
        "{point} está fora do Canadá, mas {flipped} está dentro — latitude e "
        "longitude parecem trocadas."
    ),
    "err_coord_outside_canada": (
        "{point} está fora do Canadá. Esta página cobre apenas o Canadá — use "
        "a página do Brasil para coordenadas sul-americanas."
    ),
    "err_earth_engine_query": "Falha ao consultar o Earth Engine: {exc}",
    "err_no_landcover": "Nenhum dado do inventário agrícola neste ponto.",
    "err_forest_failed": "Falha ao ler os dados de floresta: {exc}",

    # --- help / cite --------------------------------------------------------- #
    "help_trigger": "Como usar",
    "help_dialog_title": "Como usar o Naturametrics Canadá",
    "help_dialog_desc": (
        "História do inventário agrícola, idade e mudança da floresta em "
        "qualquer ponto do Canadá."
    ),
    "help_step1_title": "Escolha um ponto",
    "help_step1_body": (
        "Clique em qualquer lugar do Canadá. Um marcador é criado e quatro "
        "áreas de análise (1, 2, 5 e 10 km de raio) são desenhadas em volta "
        "dele. Cliques fora do Canadá são recusados; cliques no extremo norte "
        "não são — veja a nota sobre cobertura abaixo."
    ),
    "help_step2_title": "Leia a história do inventário agrícola",
    "help_step2_body": (
        "O gráfico abaixo do mapa traz uma coluna por ano, de 2009 a 2025, nas "
        "cores oficiais da legenda AAFC. Troque o raio em 1/2/5/10 km e use o "
        "botão «%» para alternar entre hectares e proporção da área."
    ),
    "help_step3_title": "Atenção à cobertura",
    "help_step3_body": (
        "O Inventário Anual de Culturas da AAFC é um produto agrícola, não uma "
        "cobertura do solo nacional. Alcança cerca de 58°N e não mais que isso, "
        "e seus dois primeiros anos (2009, 2010) cobrem apenas as Pradarias. Ao "
        "norte desse limite o gráfico de cobertura fica vazio enquanto os "
        "painéis de floresta continuam respondendo — o inventário simplesmente "
        "não chega lá."
    ),
    "help_step4_title": "Leia a idade da floresta",
    "help_step4_body": (
        "O NTEMS publica uma idade medida do povoamento para cada pixel "
        "florestal do Canadá, referente a 2019. O histograma agrupa a área "
        "florestal de cada buffer por idade; o resumo ao lado dá a faixa "
        "mediana e quanto do buffer é floresta. Pixels sem valor não são "
        "floresta, em vez de estarem faltando."
    ),
    "help_step5_title": "Leia a mudança florestal",
    "help_step5_body": (
        "O Hansen Global Forest Change dá a perda de cobertura arbórea ano a "
        "ano, de 2001 a 2025, mais um indicador de ganho. O controle «Limiar "
        "de floresta» define qual porcentagem de dossel em 2000 conta como "
        "floresta — aumente-o para restringir a contagem a povoamentos mais "
        "densos."
    ),
    "help_step6_title": "Troque as imagens",
    "help_step6_body": (
        "A seção Landsat desenha um composto anual sem nuvens sobre o mapa "
        "base, em cor natural ou falsa-cor infravermelha, para qualquer ano de "
        "1984 a 2026 — útil para ver um corte ou uma queimada diretamente, e "
        "não através de uma classificação."
    ),
    "help_step7_title": "Baixe os dados",
    "help_step7_body": (
        "«Baixar dados» gera uma planilha ODS com todas as tabelas por trás "
        "dos gráficos e uma aba de metadados explicando como cada número foi "
        "calculado."
    ),
    "help_limitations_title": "Limitações que valem conhecer",
    "help_limit_1": (
        "O inventário agrícola cobre apenas o sul agrícola, até cerca de 58°N, "
        "e só é nacional a partir de 2011."
    ),
    "help_limit_2": (
        "A idade da floresta é um retrato de 2019. Um povoamento indicado como "
        "de 40 anos tem cerca de 46 hoje; o aplicativo não envelhece os "
        "números, porque isso inventaria uma precisão que o raster não tem."
    ),
    "help_limit_3": (
        "O ganho do Hansen não tem data — é um único indicador para 2000–2012 "
        "no produto original — então não pode ser filtrado por ano como a "
        "perda."
    ),
    "help_limit_4": (
        "Resolução de 30 m: num raio de 1 km cabem cerca de 3.500 pixels, "
        "então poucos pixels mal classificados já mexem nas porcentagens."
    ),

    "cite_trigger": "Como citar",
    "cite_dialog_title": "Como citar",
    "cite_dialog_desc": (
        "Se o Naturametrics Canadá contribuiu para o seu trabalho, cite-o e "
        "cite também as bases de dados utilizadas."
    ),
    "cite_sources_title": "Bases de dados — cite também",
    "cite_sources_desc": (
        "Cada base tem exigências próprias de atribuição. Ao publicar figuras "
        "ou números obtidos aqui, cite as que foram usadas."
    ),
    "cite_example_title": "Exemplo de uso no texto",
    "cite_example_body": (
        "\"A área de estudo no Canadá foi analisada com o Naturametrics "
        "(Biondo et al., 2026), a partir de dados do AAFC Annual Crop "
        "Inventory e do Hansen Global Forest Change (Hansen et al., 2013).\""
    ),
}
