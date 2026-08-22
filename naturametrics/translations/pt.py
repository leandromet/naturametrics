"""Portuguese — canonical key set. Every other language falls back to this."""

from __future__ import annotations

TRANSLATIONS_PT: dict[str, str] = {
    # --- header / drawer ------------------------------------------------- #
    "nav_toggle_layers_aria": "Abrir painel de camadas",
    "nav_subtitle": "História de uso da terra e análise da paisagem",
    "drawer_title": "Camadas e análise",
    "drawer_close_aria": "Fechar painel",

    # --- layer panel: sections -------------------------------------------- #
    "section_basemap": "Mapa base",
    "section_landcover": "Cobertura do solo",
    "section_buffer_preview": "Uso no buffer",
    "section_compare": "Comparar dois anos",
    "section_change_mask": "Mudança na vegetação natural",
    "section_ifn": "Inventário Florestal Nacional",
    "filters_label": "Filtros",
    "ifn_filters_title": "Filtros do IFN",
    "section_user_points": "Coordenadas enviadas",
    "section_multi_select": "Seleção múltipla",
    "section_biomes": "Biomas (IBGE)",
    "section_biomass": "Biomassa (ESA CCI)",
    "section_forest_change": "Mudança florestal (Hansen)",
    "hansen_treecover_toggle": "Cobertura arbórea 2000",
    "hansen_change_toggle": "Perda e ganho",
    "hansen_loss_label": "Perda",
    "hansen_gain_label": "Ganho",
    "hansen_threshold_label": "Limiar de floresta (% de dossel em 2000)",
    "section_point": "Ponto de estudo",
    "buffer_square_toggle_label": "Usar buffers quadrados (lado = diâmetro)",
    "buffer_caption_square": "(lado quadrado)",
    "buffer_caption_circle": "(raio círculo)",
    "multi_shape_change_note": "Altere o formato antes de selecionar pontos múltiplos.",

    "year_label": "Ano",
    "opacity_label": "Opacidade",
    "opacity_label_compare": "Opacidade — ano à direita",
    "clear_button": "Limpar",
    "reset_button": "Reset",

    "buffer_preview_toggle_label": "Mostrar Uso no Buffer",
    "buffer_preview_text": (
        "Ao passar o cursor sobre um conglomerado — ou ao escolher um ponto "
        "— o MapBiomas aparece só dentro do raio de análise, no ano "
        "selecionado acima. Não consulta o Earth Engine: usa os mesmos "
        "blocos já pré-carregados."
    ),
    "buffer_preview_hidden_note": (
        "Oculta enquanto «MapBiomas 10.1» está ligado — a cobertura já "
        "aparece no mapa inteiro."
    ),

    "compare_toggle_label": "Cortina deslizante",
    "compare_year_left": "Ano à esquerda",
    "compare_opacity_left": "Opacidade — ano à esquerda",
    "compare_note": (
        "Arraste a linha branca no mapa. À direita fica o ano selecionado "
        "acima em «Cobertura do solo»."
    ),

    "change_mask_toggle_label": "Candidatos a recuperação",
    "change_base_year": "Ano base",
    "change_loss_label": "Perda de vegetação natural",
    "change_gain_label": "Regeneração",
    "change_mask_callout": (
        "2008 é o marco do Código Florestal: vegetação nativa suprimida "
        "depois dessa data tem obrigação de recomposição. Esta camada é "
        "uma triagem, não um laudo — não considera CAR, APP/RL, porte do "
        "imóvel nem autorizações."
    ),

    "ifn_toggle_label": "Conglomerados",
    "filter_all": "Todos",
    "filter_region": "Região",
    "filter_biome": "Bioma",
    "filter_uf": "Estado",
    "filter_municipality": "Município",
    "ifn_empty_callout": "Nenhum conglomerado nesta combinação de filtros.",
    "ifn_municipality_hint": "Escolha um estado para listar os municípios.",
    "ifn_count_label_one": "conglomerado",
    "ifn_count_label_many": "conglomerados",

    "user_points_active_note": "Ativa no mapa no lugar dos conglomerados do IFN.",

    "multi_toggle_label": "Somar vários conglomerados",
    "multi_help_text": (
        "Clique nos conglomerados para incluir ou remover, ou segure Ctrl "
        "(Cmd no Mac) e arraste para selecionar uma área inteira. O gráfico "
        "passa a mostrar a soma das áreas de cada raio. Shift+arrastar "
        "continua sendo o zoom por área do mapa, e cliques avulsos ficam "
        "desativados enquanto o modo está ligado."
    ),
    "multi_label_one": "Soma de 1 conglomerado",
    "multi_label_many": "Soma de {n} conglomerados",
    "multi_blocked_point_error": (
        "Seleção múltipla ativa: clique nos conglomerados para incluí-los "
        "ou removê-los. Desligue o modo para escolher um ponto avulso."
    ),
    "multi_view_sum": "Soma",
    "multi_view_full_area": "Área total",
    "multi_full_area_failed": "Falha ao calcular a área total: {exc}",

    "biomes_toggle_label": "Biomas e domínios",
    "biomes_hover_note": (
        "Passe o cursor sobre um polígono para ver bioma, domínio "
        "fitogeográfico e região natural. Os limites estão simplificados "
        "(~1 km) para desenho no navegador."
    ),

    "point_click_other": "Clique no mapa para escolher outro ponto.",
    "point_click_choose": "Clique no mapa para escolher um ponto.",

    "basemap_unavailable": (
        "«{label}» indisponível — a conta pode não ter aceitado a licença "
        "deste conjunto."
    ),

    "status_ee_unavailable": "Earth Engine indisponível",
    "status_ee_connecting": "Conectando ao Earth Engine…",
    "status_ee_prefetching": "Pré-carregando anos… {done}/{total}",
    "status_ee_ready": "Earth Engine pronto — {done} anos em cache",

    # --- results drawer ----------------------------------------------------- #
    "landuse_title": "História de uso da terra",
    "download_button": "Baixar dados",
    "download_point_aria": "Baixar dados deste ponto",
    "analysis_running": "Reduzindo 40 anos sobre 4 buffers…",
    "full_area_running": "Reduzindo 40 anos sobre a caixa delimitadora…",
    "top_classes_title": "Classes principais (2024)",
    "area_natural_label": "Área natural (registrada)",
    "median_label": "Mediana (datada)",
    "no_change_label": "Sem alteração observada",
    "change_title": "Mudança 2008→2024",
    "vegetation_age_title": "Idade da vegetação",
    "landscape_metrics_tab": "Métricas de paisagem",
    "landscape_metrics_empty": "Métricas ainda não disponíveis.",
    "err_landscape_metrics_failed": "Falha ao calcular as métricas de paisagem: {exc}",
    "metrics_buffer": "Buffer",
    "metrics_area": "Área (ha)",
    "metrics_patches": "Manchas",
    "metrics_patch_density": "Manchas/ha",
    "metrics_lpi": "Maior mancha (%)",
    "metrics_edge_density": "Borda (m/ha)",
    "metrics_shannon": "Shannon",
    "metrics_simpson": "Simpson",
    "metrics_evenness": "Equidade",
    "biomass_tab": "Biomassa",
    "biomass_running": "Lendo a biomassa acima do solo (ESA CCI)…",
    "biomass_empty": "Biomassa ainda não disponível.",
    "err_biomass_failed": "Falha ao calcular a biomassa: {exc}",
    "age_running": "Lendo a série de desmatamento e vegetação secundária…",
    "empty_state_title": "Clique no mapa para escolher um ponto",
    "empty_state_body": (
        "A história de uso da terra e a idade da vegetação, de 1985/1987 a "
        "2024, serão calculadas para raios de 1, 2, 5 e 10 km em volta dele."
    ),

    # --- export dialog ------------------------------------------------------ #
    "export_dialog_title": "Baixar dados",
    "export_dialog_desc": (
        "Cada download é uma planilha ODS com uma aba por tabela e uma aba "
        "de metadados com a proveniência completa. Abre no LibreOffice, no "
        "Excel e no Google Planilhas."
    ),
    "close_button": "Fechar",
    "no_point_badge": "nenhum ponto",
    "study_point_desc": (
        "Uma planilha com: o pixel do próprio ponto ano a ano, uma aba por "
        "raio ({radii} km) com a série completa 1985–2024, um resumo de "
        "variação por classe, o dicionário de classes do MapBiomas e a aba "
        "de metadados com a proveniência de cada consulta."
    ),
    "download_point_button": "Baixar planilha do ponto (.ods)",
    "download_point_hint": "Clique num ponto ou num conglomerado do mapa para habilitar.",
    "selection_title_submitted": "Lista enviada",
    "selection_title_default": "Seleção de conglomerados",
    "selection_note": (
        "Sai ponto a ponto, um conglomerado por linha — a soma que aparece "
        "no gráfico é uma leitura, não o formato do arquivo."
    ),
    "check_points_label": "Lista de conglomerados",
    "check_points_detail": (
        "Um por linha: identificador, região, UF, município, bioma e "
        "coordenadas. Instantâneo."
    ),
    "check_pixel_label": "Classe do pixel, ano a ano",
    "check_pixel_detail": (
        "O pixel de 30 m de cada conglomerado, uma coluna por ano de 1985 a "
        "2024. Sem limite de tamanho — a seleção inteira sai em segundos."
    ),
    "check_buffers_label": "Histórico dos buffers ({radii} km)",
    "check_buffers_detail": (
        "Área por classe e por ano, para cada conglomerado — a mesma conta "
        "que o gráfico faz. Uma aba por raio, mais idade da vegetação, "
        "métricas de paisagem e biomassa. É a parte cara: exportar um raio "
        "só deixa o arquivo bem menor e mais rápido."
    ),
    "check_full_area_label": "Área total (caixa delimitadora)",
    "check_full_area_detail": (
        "Uma caixa única envolvendo o buffer de cada conglomerado "
        "selecionado, sem sobreposição contada duas vezes — mas incluindo "
        "também a área entre eles. Quatro abas extras: uso da terra, idade "
        "da vegetação, métricas de paisagem e biomassa. Só disponível na "
        "seleção manual."
    ),
    "export_radii_label": "Raios a exportar",
    "cancel_button": "Cancelar",
    "confirm_download_button": "Confirmar e baixar",
    "download_selection_button": "Baixar planilha da seleção (.ods)",
    "provenance_callout": (
        "Nenhum número sai daqui sem proveniência: a aba «metadados» diz "
        "qual coleção, quais bandas, qual escala e qual redutor produziram "
        "cada tabela, e traz as atribuições que devem ser citadas."
    ),
    "export_source_map_filters": "Filtros do mapa",
    "export_source_manual_prefix": "Seleção manual",
    "export_selection_user_points": "{n} pontos da lista enviada",
    "export_selection_manual": "{n} conglomerados escolhidos no mapa",
    "export_selection_whole_country": "Brasil inteiro (sem filtro)",
    "export_count_one": "conglomerado",
    "export_count_many": "conglomerados",
    "export_radius_all": "Todos os raios",
    "export_no_selection": "Nenhum conglomerado na seleção atual.",
    "export_choose_point_first": "Escolha um ponto no mapa primeiro.",
    "export_stage_building_point": "Montando a planilha do ponto",
    "export_stage_waiting_age": "Aguardando a idade da vegetação…",
    "export_stage_computing_landuse": "Calculando o uso da terra",
    "export_stage_computing_age": "Calculando a idade da vegetação",
    "export_stage_computing_change": "Calculando a mudança 2008→2024",
    "export_stage_computing_metrics": "Calculando as métricas de paisagem",
    "export_stage_computing_biomass": "Calculando a biomassa",
    "export_stage_computing_full_area": "Calculando a área total",
    "export_stage_building_sheet": "Montando a planilha",
    "export_stage_gathering": "Reunindo os conglomerados",
    "export_stage_reading_pixel": "Lendo o pixel de cada conglomerado",
    "export_no_datasets": "Marque pelo menos um conjunto de dados.",
    "export_sheet_failed": "Falha ao gerar a planilha: {exc}",
    "export_result_failed_note": " · {n} conglomerado(s) falharam",

    # --- submit-coordinates dialog ------------------------------------------ #
    "send_button": "Enviar dados",
    "send_list_aria": "Enviar lista de coordenadas",
    "send_dialog_title": "Enviar lista de coordenadas",
    "send_dialog_desc": (
        "Cole uma lista de pontos — um por linha — para usá-la no mapa no "
        "lugar dos conglomerados do IFN: passar o mouse ou clicar em um "
        "ponto passa a se referir a esta lista, e a análise completa de "
        "todos os pontos pode ser baixada depois. Apenas colar texto é "
        "aceito, não upload de arquivo."
    ),
    "send_format_label": "Formato: nome (opcional), latitude, longitude",
    "send_max_points": "Até {max} pontos por lista.",
    "send_active_points": "{n} pontos ativos",
    "send_truncated": (
        "A lista tem mais de {max} pontos válidos; apenas os primeiros "
        "{max} foram mantidos."
    ),
    "submit_button": "Enviar",

    # --- coordinate validation ------------------------------------------ #
    "err_coord_swapped": (
        "{point} está fora do Brasil, mas {flipped} está dentro — latitude "
        "e longitude parecem trocadas."
    ),
    "err_coord_outside_brazil": (
        "{point} está fora do Brasil. O MapBiomas cobre apenas o Brasil, "
        "portanto não há histórico de cobertura do solo para este local."
    ),

    # --- provenance line ----------------------------------------------------- #
    "years_unit": "anos",
    "provenance_degraded": " · resultado degradado",
    "provenance_summed_one": " · soma de 1 conglomerado (buffers sobrepostos são contados em cada um)",
    "provenance_summed_many": " · soma de {n} conglomerados (buffers sobrepostos são contados em cada um)",
    "provenance_full_area_one": " · área total de 1 conglomerado (caixa delimitadora, inclui área entre pontos)",
    "provenance_full_area_many": " · área total de {n} conglomerados (caixa delimitadora, inclui área entre pontos)",

    # --- conglomerado hover card / multi-select -------------------------- #
    "hover_no_coverage": "Sem cobertura mapeada neste raio.",
    "hover_natural_template": "Vegetação natural {last}% (era {first}% em {year})",
    "hover_note_template": (
        "Composição em {year} num raio de {radius} km. Clique para a "
        "análise completa."
    ),
    "hover_coords_unavailable": "Coordenadas do conglomerado indisponíveis.",
    "hover_read_failed": "Não foi possível ler a cobertura aqui.",
    "multi_limit_reached": (
        "Limite de {max} conglomerados na seleção. Remova algum para "
        "incluir outro."
    ),
    "multi_analysis_failed": "Falha ao analisar {key}: {exc}",
    "multi_area_none_new": "Nenhum conglomerado novo nessa área.",
    "multi_area_none": "Nenhum conglomerado nessa área.",
    "multi_area_limit_reached": "Limite de {max} conglomerados atingido.",
    "multi_area_truncated": (
        "Área com mais conglomerados que o limite — incluídos os "
        "primeiros {n}."
    ),
    "multi_area_failed": "{n} conglomerado(s) falharam.",

    # --- analysis errors --------------------------------------------------- #
    "err_earth_engine_query": "Falha ao consultar o Earth Engine: {exc}",
    "err_no_landcover": "Nenhuma cobertura do solo encontrada neste ponto.",
    "err_vegetation_age_failed": "Falha ao calcular a idade da vegetação: {exc}",
    "err_no_vegetation_age": "Sem dados de idade da vegetação neste ponto.",

    # --- "Como usar" dialog ------------------------------------------------ #
    "help_trigger": "Como usar",
    "help_dialog_title": "Como usar o Naturametrics",
    "help_dialog_desc": (
        "Análise da história de uso da terra e da paisagem em qualquer "
        "ponto do Brasil."
    ),
    "help_step1_title": "Escolha um ponto",
    "help_step1_body": (
        "Clique em qualquer lugar do mapa. Um marcador é criado e quatro "
        "áreas de análise (1, 2, 5 e 10 km de raio) são desenhadas em volta "
        "dele. Cliques fora do Brasil são recusados: o MapBiomas cobre "
        "apenas o território nacional."
    ),
    "help_step2_title": "Leia a história de uso da terra",
    "help_step2_body": (
        "O gráfico abaixo do mapa traz uma coluna por ano, de 1985 a 2024, "
        "com as classes do MapBiomas nas cores oficiais. Troque o raio em "
        "1/2/5/10 km e use o botão «%» para alternar entre hectares e "
        "proporção da área."
    ),
    "help_step3_title": "Troque o mapa base",
    "help_step3_body": (
        "O padrão é o híbrido do Google, que traz nomes de municípios e "
        "estradas — útil para conferir onde você está. A lista inclui "
        "ainda o mosaico SPOT de 2008 do Brasil, em cor natural e em "
        "falsa-cor infravermelha: ele cobre só as áreas florestais do "
        "país, então há vazios fora desse recorte, e fica desenhado por "
        "cima do mapa base escolhido antes."
    ),
    "help_step4_title": "Veja a cobertura no mapa",
    "help_step4_body": (
        "Ligue «MapBiomas 10.1» na barra lateral. O controle «Ano» percorre "
        "1985–2024 — todos os anos são pré-carregados, então a troca é "
        "imediata e o mapa não sai do lugar. «Opacidade» controla o quanto "
        "do mapa base aparece por baixo."
    ),
    "help_step5_title": "Compare dois anos",
    "help_step5_body": (
        "«Cortina deslizante» mostra dois anos ao mesmo tempo, separados "
        "por uma linha branca que você arrasta pelo mapa. O ano da "
        "esquerda é escolhido no próprio painel; o da direita é o ano "
        "selecionado em «Cobertura do solo». Cada lado tem sua própria "
        "opacidade."
    ),
    "help_step6_title": "Encontre candidatos a recuperação",
    "help_step6_body": (
        "«Mudança na vegetação natural» destaca em vermelho o que era "
        "vegetação natural no ano base e deixou de ser, e em verde o que "
        "regenerou. O padrão é 2008, marco do Código Florestal: supressão "
        "posterior a 22/07/2008 tem obrigação de recomposição."
    ),
    "help_step7_title": "Trabalhe com os conglomerados do IFN",
    "help_step7_body": (
        "Ligue «Conglomerados» na barra lateral para ver os 17.479 pontos "
        "do Inventário Florestal Nacional, e filtre por região, bioma, "
        "estado e município — o mapa enquadra a seleção sozinho. "
        "Aproximando o zoom, os pontos ficam interativos: pare o cursor "
        "sobre um para ver a cobertura num raio de 10 km hoje e em 1985 — "
        "e o próprio mapa mostra o MapBiomas só dentro desse raio, no ano "
        "escolhido. Clique para rodar a análise completa nas coordenadas "
        "oficiais dele."
    ),
    "help_step8_title": "Some vários conglomerados",
    "help_step8_body": (
        "Ligue «Seleção múltipla» na barra lateral e clique nos "
        "conglomerados que interessam — clicar de novo remove — ou segure "
        "Ctrl (Cmd no Mac) e arraste para pegar uma área inteira de uma "
        "vez. O gráfico passa a mostrar a soma das áreas de cada raio em "
        "todos eles, e o mapa desenha os buffers de todos ao mesmo tempo. "
        "Atenção: buffers que se sobrepõem são contados uma vez em cada "
        "conglomerado, então o total não é a área da união."
    ),
    "help_step9_title": "Baixe os dados",
    "help_step9_body": (
        "Em «Baixar dados», no topo da página. São duas planilhas ODS "
        "independentes: a do ponto de estudo atual, com uma aba por raio e "
        "o pixel do próprio ponto ano a ano; e a da seleção de "
        "conglomerados — pelos filtros do mapa ou pelos pontos escolhidos "
        "à mão — onde você marca o que quer: lista de pontos, classe do "
        "pixel ano a ano, e o histórico dos buffers — com uma aba por "
        "raio, e a opção de exportar um raio só, que faz caber muito mais "
        "conglomerados. Toda planilha abre com uma aba «metadados» "
        "dizendo como cada número foi calculado."
    ),
    "help_step10_title": "Idade, métricas de paisagem e biomassa",
    "help_step10_body": (
        "Ao lado da história de uso da terra, três abas trazem outras "
        "leituras da mesma área: «Idade da vegetação» mostra a série de "
        "desmatamento e regeneração; «Métricas de paisagem» calcula número "
        "e tamanho das manchas, densidade de borda e diversidade de classes "
        "(NP, PD, LPI, ED, Shannon, Simpson); e «Biomassa» lê a biomassa "
        "acima do solo do ESA CCI Biomass_cci — 2007, 2010 e anualmente de "
        "2015 a 2022. As três funcionam tanto para um ponto quanto para a "
        "soma ou a área total de uma seleção múltipla."
    ),
    "help_triage_callout": (
        "Esta camada é uma triagem, não um laudo. Não considera CAR, "
        "APP/Reserva Legal, porte do imóvel nem autorizações de "
        "supressão. Use-a para orientar a investigação, não para "
        "concluí-la."
    ),
    "help_limitations_title": "Limitações que valem conhecer",
    "help_limit_1": (
        "Resolução de 30 m: num raio de 1 km cabem cerca de 3.500 pixels, "
        "então poucos pixels mal classificados já mexem nas porcentagens."
    ),
    "help_limit_2": (
        "A série do MapBiomas começa em 1985 — não é possível saber a "
        "idade de vegetação que já existia antes disso."
    ),
    "help_limit_3": (
        "As áreas são calculadas com a área real do pixel "
        "(ee.Image.pixelArea), que varia com a latitude; um valor fixo de "
        "0,09 ha superestimaria a área."
    ),
    "help_limit_4": (
        "As classes do MapBiomas não são seguras para daltonismo — a "
        "legenda sempre traz o nome ao lado da cor."
    ),

    # --- "Como citar" dialog ------------------------------------------------ #
    "cite_trigger": "Como citar",
    "cite_dialog_title": "Como citar",
    "cite_dialog_desc": (
        "Se o Naturametrics contribuiu para o seu trabalho, cite-o e cite "
        "também as bases de dados utilizadas."
    ),
    "cite_suggested_title": "Citação sugerida",
    "cite_copy_citation": "Copiar citação",
    "cite_bibtex_title": "BibTeX",
    "cite_copy_bibtex": "Copiar BibTeX",
    "cite_authors_title": "Autores e instituições",
    "cite_sources_title": "Bases de dados — cite também",
    "cite_sources_desc": (
        "Cada base tem exigências próprias de atribuição. Ao publicar "
        "figuras ou números obtidos aqui, cite as que foram usadas."
    ),
    "cite_example_title": "Exemplo de uso no texto",
    "cite_example_body": (
        "\"A área de estudo foi analisada com o Naturametrics (Biondo et "
        "al., 2026), a partir de dados do MapBiomas Coleção 10.1 e do "
        "Hansen Global Forest Change (Hansen et al., 2013).\""
    ),
    "cite_spot_callout": (
        "As imagens SPOT 2008 (Brazil Forest Imagery Dataset) exigem "
        "aceite de licença específica do Google e ainda não estão "
        "habilitadas nesta instância."
    ),

    # --- AI-disclaimer dialog ------------------------------------------------ #
    "ai_trigger": "Aviso sobre uso de IA",
    "ai_dialog_desc": "Como este aplicativo foi construído, e com que ajuda.",
    "ai_para1": (
        "O código do Naturametrics foi escrito com assistência de modelos "
        "de IA da Anthropic — Claude Opus e Claude Sonnet —, sob "
        "supervisão e revisão do autor em cada etapa. A arquitetura, os "
        "padrões de estado e a maior parte das convenções de interface "
        "partem do Yvynation, uma plataforma irmã já madura para análise "
        "de terras indígenas, também desenvolvida com o mesmo processo."
    ),
    "ai_para2": (
        "Isso significa que grandes trechos deste aplicativo — desde a "
        "integração com o Earth Engine até os componentes de interface — "
        "foram adaptados ou reescritos a partir do que já funcionava no "
        "Yvynation, em vez de criados do zero."
    ),
    "ai_see_yourself_title": "Veja por si mesmo",
    "ai_yvynation_link": "Yvynation — aplicativo em produção",

    # --- language switcher ---------------------------------------------- #
    "go_to_canada": "Ir para o Canadá",
    "language_label": "Idioma",
}
