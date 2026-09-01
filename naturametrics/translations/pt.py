"""Portuguese — canonical key set. Every other language falls back to this."""

from __future__ import annotations

TRANSLATIONS_PT: dict[str, str] = {
    # --- header / drawer ------------------------------------------------- #
    "nav_toggle_layers_aria": "Abrir painel de camadas",
    "nav_subtitle": "História de uso da terra e análise da paisagem",
    "drawer_title": "Camadas e análise",
    "drawer_close_aria": "Fechar painel",
    "sheet_handle_aria": "Redimensionar painel — arraste ou use as setas",

    # --- layer panel: sections -------------------------------------------- #
    "section_basemap": "Mapa base",
    "section_landcover": "Cobertura do solo",
    "section_compare": "Comparar camadas",
    "section_change_mask": "Mudança na vegetação natural",
    "section_ifn": "Inventário Florestal Nacional",
    "section_embargos": "Embargos IBAMA",
    "section_auto_infracao": "Autos de infração IBAMA",
    "filters_label": "Filtros",
    "ifn_filters_title": "Filtros do IFN",
    "section_user_points": "Coordenadas enviadas",
    "section_multi_select": "Seleção múltipla",
    "section_biomes": "Biomas (IBGE)",
    "section_biomass": "Biomassa (ESA CCI)",
    "section_ibge_veg": "Vegetação (IBGE 2022)",
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
    "radius_selector_hint": (
        "Alterna o gráfico e a tabela entre os tamanhos de buffer ao redor "
        "do ponto — um raio maior cobre mais área, mas perde detalhe local."
    ),
    "multi_shape_change_note": "Altere o formato antes de selecionar pontos múltiplos.",

    # --- busca de localização ------------------------------------------------ #
    "search_title": "Buscar",
    "search_placeholder": "Coordenada, município ou nome de lugar…",
    "search_read_as": "lido como:",
    "search_button": "Buscar",
    "search_button_busy": "Buscando…",
    "search_municipios_heading": "Municípios",
    "search_places_heading": "Lugares",
    "search_places_attribution": "© colaboradores do OpenStreetMap (ODbL)",
    "search_place_hint": "clique no mapa para escolher um ponto",
    "echo_coordenada": "coordenada",
    "echo_municipio": "município",
    "echo_lugar": "lugar",
    "erro_lugar_nao_encontrado": "Nenhum lugar encontrado para “{query}”.",

    # --- layer panel: info-icon popovers ---------------------------------- #
    # One per sidebar section — what it is and when it helps understand a
    # study area, in a couple of sentences a popover can hold comfortably.
    "search_info": (
        "Busque uma coordenada, um município ou um nome de lugar para "
        "navegar pelo mapa. Um município ou lugar apenas enquadra o "
        "mapa; uma coordenada exata também a escolhe como ponto de "
        "estudo, o mesmo que clicar ali."
    ),
    "point_info": (
        "Clique em qualquer lugar do Brasil para escolher um ponto de "
        "estudo. A aplicação calcula automaticamente uso do solo, idade da "
        "vegetação, métricas de paisagem, biomassa e comparação com o IBGE "
        "em cinco raios ao redor do ponto (0,5 a 10 km) — a forma mais "
        "rápida de começar a entender um lugar específico. \"Mostrar Uso "
        "no Buffer\" mostra o MapBiomas do ano selecionado em «Cobertura "
        "do solo» só dentro desses raios ao passar o cursor — uma prévia "
        "rápida e gratuita, sem consulta ao Earth Engine, antes de rodar a "
        "análise completa."
    ),
    "geometry_info": (
        "Desenhe um polígono/retângulo no mapa, cole um WKT ou envie um KML "
        "para analisar uma área exata em vez de um raio ao redor de um "
        "ponto — útil quando você já tem o contorno de uma propriedade, "
        "unidade de conservação ou outro polígono de interesse. Enquanto "
        "\"Desenhar no mapa\" está ativo, um clique no mapa não escolhe "
        "mais um ponto — use as ferramentas de polígono/retângulo no canto "
        "do mapa. Colar um WKT ou enviar um KML em \"Enviar dados\" não "
        "exige ativar isto."
    ),
    "basemap_info": (
        "Escolha a imagem de fundo do mapa. As opções SPOT 2008 mostram "
        "fotos reais de satélite de ~2008 — o marco do Código Florestal — "
        "permitindo conferir a olho se uma área realmente tinha vegetação "
        "naquele ano, algo que o MapBiomas (classificado, não é foto) não "
        "mostra diretamente."
    ),
    "mapbiomas_info": (
        "Cobertura do solo classificada pelo MapBiomas, ano a ano desde "
        "1985. É a base de toda a análise de uso da terra do aplicativo — "
        "ligue para ver o que está mudando (ou não) na área de estudo ao "
        "longo do tempo."
    ),
    "compare_info": (
        "Compare duas versões da mesma área lado a lado, com uma linha "
        "divisória arrastável: dois anos do MapBiomas (antes/depois), IBGE "
        "× MapBiomas (checagem cruzada de classificação), os dois mosaicos "
        "SPOT 2008 entre si (cor natural × infravermelho), ou o MapBiomas "
        "2008/IBGE contra o SPOT 2008 — validando uma classificação direto "
        "contra a imagem real do ano-base do Código Florestal."
    ),
    "change_mask_info": (
        "Destaca onde a vegetação natural existente no ano-base (padrão "
        "2008, o marco do Código Florestal — Lei 12.651/2012) foi perdida "
        "ou está se regenerando até hoje. Uma ferramenta de triagem para "
        "candidatos à restauração — não é uma constatação legal; sempre "
        "confira caso a caso."
    ),
    "ifn_info": (
        "Mostra os pontos de amostragem do Inventário Florestal Nacional, "
        "filtráveis por região/UF/município/bioma. Cada ponto pode ser "
        "clicado como um clique no mapa, com a vantagem de já ter "
        "identidade e localização publicadas — útil para comparar com "
        "dados de campo."
    ),
    "embargos_info": (
        "Áreas embargadas pelo IBAMA por infrações ambientais, buscadas "
        "ao vivo do próprio serviço do IBAMA para a área visível. "
        "Atualizado no ritmo do IBAMA, fora do controle deste app — pode "
        "ficar temporariamente esparso ou indisponível, independente "
        "daqui."
    ),
    "auto_infracao_info": (
        "Autos de infração emitidos pelo IBAMA, um a um, buscados ao "
        "vivo para a área visível — um dado complementar aos embargos: "
        "o auto é a autuação em si; o embargo é a restrição que pode "
        "vir depois dela, e nem toda autuação gera um embargo. Muito "
        "mais denso que os embargos, por isso só aparece com o zoom "
        "mais fechado."
    ),
    "user_points_info": (
        "Substitui a grade do IFN por uma lista de pontos definida por "
        "você — colada como coordenadas, WKT, ou enviada como KML (veja "
        "\"Enviar dados\" no topo da página). Útil para analisar seus "
        "próprios locais de interesse em lote."
    ),
    "multi_select_info": (
        "Soma vários pontos/conglomerados em uma análise única, como se "
        "fossem um só lugar. Ligue, clique em vários pontos no mapa (ou "
        "arraste uma área) e veja o total combinado — útil para "
        "caracterizar uma região inteira, não só um ponto isolado."
    ),
    "biomes_info": (
        "Contorno dos biomas brasileiros (IBGE) — passe o cursor sobre um "
        "polígono para ver bioma, domínio fitogeográfico e região natural. "
        "Os limites estão simplificados (~1 km) para desenho no navegador. "
        "Ajuda a situar a área de estudo no contexto biogeográfico mais "
        "amplo do país."
    ),
    "biomass_info": (
        "Biomassa acima do solo (toneladas por hectare) do produto ESA CCI "
        "Biomass, em dez anos entre 2007 e 2022. Estima quanto carbono está "
        "armazenado na vegetação da área — um complemento à classificação "
        "de cobertura do solo do MapBiomas."
    ),
    "ibge_veg_info": (
        "Classificação de vegetação do IBGE (2022), numa escala mais "
        "detalhada de 1:250.000. Serve como segunda opinião independente "
        "sobre o que está mapeado como vegetação natural — compare com o "
        "MapBiomas na seção \"Comparar camadas\" acima."
    ),
    "hansen_info": (
        "Cobertura arbórea do ano 2000 e perda/ganho florestal (Hansen "
        "Global Forest Change), um produto internacional independente do "
        "MapBiomas — útil para confirmar tendências de desmatamento com "
        "outra fonte de dados."
    ),

    "year_label": "Ano",
    "opacity_label": "Opacidade",
    "opacity_label_compare": "Opacidade — ano à direita",
    "clear_button": "Limpar",
    "reset_button": "Reset",

    "buffer_preview_toggle_label": "Mostrar Uso no Buffer",
    "buffer_preview_hidden_note": (
        "Oculta enquanto «MapBiomas 10.1» está ligado — a cobertura já "
        "aparece no mapa inteiro."
    ),

    "compare_mode_off": "Nenhuma",
    "compare_mode_years": "MapBiomas — dois anos",
    "compare_mode_ibge": "IBGE × MapBiomas",
    "compare_mode_spot": "SPOT 2008 — Visual × NIR",
    "compare_mode_mb_spot_visual": "MapBiomas 2008 × SPOT 2008 Visual",
    "compare_mode_mb_spot_analytic": "MapBiomas 2008 × SPOT 2008 NIR",
    "compare_mode_ibge_spot_visual": "IBGE × SPOT 2008 Visual",
    "compare_mode_ibge_spot_analytic": "IBGE × SPOT 2008 NIR",
    "compare_year_left": "Ano à esquerda",
    "compare_opacity_left": "Opacidade — ano à esquerda",
    "compare_note": (
        "Arraste a linha branca no mapa. À direita fica o ano selecionado "
        "acima em «Cobertura do solo»."
    ),
    "spot_compare_note": (
        "Arraste a linha branca no mapa. Visual (cores naturais) à direita, "
        "falsa-cor infravermelho à esquerda — o mesmo mosaico de 2008, duas "
        "combinações de bandas."
    ),
    "mb_spot_visual_note": (
        "Arraste a linha branca no mapa. À direita fica o MapBiomas 2008 — "
        "o ano de referência do Código Florestal —, à esquerda o SPOT 2008 "
        "Visual: uma checagem visual direta da classificação para esse ano "
        "específico."
    ),
    "mb_spot_analytic_note": (
        "Arraste a linha branca no mapa. À direita fica o MapBiomas 2008, à "
        "esquerda o SPOT 2008 em falsa-cor infravermelho — o infravermelho "
        "realça vegetação viva, o que ajuda a distinguir floresta "
        "remanescente de área já convertida em 2008."
    ),
    "ibge_spot_visual_note": (
        "Arraste a linha branca no mapa. À direita fica a Vegetação IBGE "
        "2022, à esquerda o SPOT 2008 Visual — compara o remanescente atual "
        "com a paisagem no ano-base do Código Florestal."
    ),
    "ibge_spot_analytic_note": (
        "Arraste a linha branca no mapa. À direita fica a Vegetação IBGE "
        "2022, à esquerda o SPOT 2008 em falsa-cor infravermelho — o "
        "infravermelho de 2008 ajuda a ver onde a vegetação hoje "
        "classificada pelo IBGE já existia (ou não) no ano-base."
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
    "embargos_toggle_label": "Mostrar áreas embargadas",
    "embargos_note": (
        "Feed ao vivo do próprio serviço do IBAMA, atualizado por eles, "
        "não por este app — não fica em cache aqui além de alguns "
        "minutos."
    ),
    "auto_infracao_toggle_label": "Mostrar autos de infração",
    "auto_infracao_note": (
        "Só aparece com o zoom mais fechado do que os embargos — um "
        "conjunto bem mais denso no país todo. Feed ao vivo do próprio "
        "serviço do IBAMA, não fica em cache aqui além de alguns "
        "minutos."
    ),
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

    "biomes_labels_toggle_label": "Mostrar rótulos",
    "biomes_toggle_label": "Biomas e domínios",

    "point_click_other": "Clique no mapa para escolher outro ponto.",
    "point_click_choose": (
        "Clique no mapa para escolher um ponto, ou ative \"Desenhar no "
        "mapa\" para desenhar uma área."
    ),

    # --- drawn/uploaded region (services/region_geometry.py) --------------- #
    "section_geometry": "Área desenhada",
    "geometry_draw_toggle_label": "Desenhar no mapa",
    "geometry_label_drawn": "Área desenhada",
    "geometry_source_drawn": "desenho no mapa",
    "geometry_label_wkt": "Área (WKT)",
    "geometry_source_wkt": "WKT colado",
    "geometry_label_kml": "Área (KML)",
    "geometry_source_kml": "arquivo KML",

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
    "vegetation_age_tab_hint": (
        "Há quanto tempo cada mancha de vegetação natural permanece sem "
        "distúrbio, datada a partir do último ano em que o MapBiomas "
        "registrou mudança de cobertura naquele pixel."
    ),
    "landscape_metrics_tab": "Métricas de paisagem",
    "landscape_metrics_tab_hint": (
        "Fragmentação da vegetação natural neste buffer — número de "
        "manchas, densidade de borda, tamanho efetivo de malha e índices "
        "de diversidade (Shannon, Simpson)."
    ),
    "landscape_metrics_empty": "Métricas ainda não disponíveis.",
    "err_landscape_metrics_failed": "Falha ao calcular as métricas de paisagem: {exc}",
    "metrics_buffer": "Buffer",
    "metrics_area": "Área (ha)",
    "metrics_patches": "Manchas",
    "metrics_patch_density": "Manchas/ha",
    "metrics_lpi": "Maior mancha (%)",
    "metrics_edge_density": "Borda (m/ha)",
    "metrics_meff": "Meff (ha)",
    "metrics_shannon": "Shannon",
    "metrics_simpson": "Simpson",
    "metrics_evenness": "Equidade",
    "connectivity_hint": (
        "Distância média até o fragmento de floresta mais próximo (vizinho "
        "mais próximo, ENN) — mais custosa que as métricas acima porque "
        "vetoriza os fragmentos de cada buffer e faz uma busca espacial "
        "local, em vez de reaproveitar uma imagem já calculada."
    ),
    "connectivity_run_button": "Calcular conectividade (mais lento)",
    "connectivity_running": "Vetorizando fragmentos e calculando distâncias…",
    "connectivity_empty": "Ainda não calculada — clique para rodar.",
    "err_connectivity_failed": "Falha ao calcular a conectividade: {exc}",
    "connectivity_n_fragments": "Fragmentos",
    "connectivity_enn_mean": "Dist. média viz. mais próx. (m)",
    "connectivity_enn_median": "Mediana (m)",
    "export_chart_aria": "Baixar este gráfico (PNG)",
    "export_table_aria": "Baixar esta tabela (CSV)",
    "export_chart_label": "Exportar figura",
    "export_table_label": "Exportar tabela",
    "biomass_tab": "Biomassa",
    "biomass_tab_hint": (
        "Biomassa acima do solo neste buffer (ESA CCI), uma proxy de "
        "quanto carbono a vegetação em pé armazena."
    ),
    "biomass_running": "Lendo a biomassa acima do solo (ESA CCI)…",
    "biomass_empty": "Biomassa ainda não disponível.",
    "err_biomass_failed": "Falha ao calcular a biomassa: {exc}",
    "ibge_veg_tab": "IBGE × MapBiomas",
    "ibge_veg_tab_hint": (
        "Confronta a classificação de 30 m do MapBiomas com o mapa "
        "oficial de vegetação do IBGE, 1:250.000 — duas fontes "
        "independentes para o mesmo terreno."
    ),
    "ibge_veg_running": "Comparando a vegetação do IBGE com o MapBiomas 2022…",
    "ibge_veg_empty": "Comparação ainda não disponível.",
    "err_ibge_veg_failed": "Falha ao comparar a vegetação do IBGE com o MapBiomas: {exc}",
    "ibge_veg_forest_label": "Floresta",
    "ibge_veg_natural_label": "Natural",
    "ibge_veg_layer_note": (
        "Vegetação IBGE, 1:250.000 (2022) — 54 classes oficiais; cores "
        "agrupadas por família (floresta em verde, não-floresta em bege, "
        "antrópico em rosa, água em azul) para facilitar a leitura no mapa. "
        "Ative a camada com um ponto selecionado para ver as classes "
        "presentes na legenda, no canto do mapa."
    ),
    "ibge_compare_note": (
        "Arraste a linha branca no mapa. À direita fica o MapBiomas 2022, "
        "à esquerda a Vegetação IBGE 2022 — desliga a cortina de comparação "
        "de anos acima, já que o mapa tem apenas um divisor."
    ),
    "ibge_veg_caveat": (
        "Os dois conjuntos de dados são simplificados para uma taxonomia "
        "compartilhada natural/antrópico × floresta nesta comparação — não é "
        "a classificação original de nenhum dos dois. \"Antrópico — "
        "Vegetação Secundária\" (IBGE) não tem equivalente direto no "
        "MapBiomas por definição; a matriz mostra como o MapBiomas "
        "atualmente lê esses polígonos."
    ),
    "age_running": "Lendo a série de desmatamento e vegetação secundária…",
    "empty_state_title": "Clique no mapa ou desenhe uma área",
    "empty_state_body": (
        "A história de uso da terra e a idade da vegetação, de 1985/1987 a "
        "2024, serão calculadas para raios de 1, 2, 5 e 10 km em volta de um "
        "ponto — ou para toda a área, se você desenhar, colar um WKT ou "
        "enviar um KML."
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
    "report_section_title": "Relatório em HTML (formato de artigo)",
    "report_section_desc": (
        "Um único arquivo HTML autocontido com os gráficos e/ou tabelas já "
        "calculados, formatado para leitura ou impressão em PDF — "
        "complementa a planilha acima, não a substitui."
    ),
    "check_report_figures_label": "Gráficos",
    "check_report_figures_detail": (
        "Uso da terra, idade da vegetação e biomassa, um gráfico por raio de "
        "buffer."
    ),
    "check_report_tables_label": "Tabelas",
    "check_report_tables_detail": (
        "Variação de área por classe, métricas de paisagem, conectividade "
        "(se já calculada) e a proveniência de cada consulta."
    ),
    "download_report_button": "Baixar relatório (HTML)",
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
    "check_connectivity_label": "Conectividade (vizinho mais próximo)",
    "check_connectivity_detail": (
        "Distância média/mediana ao fragmento de floresta mais próximo, por "
        "conglomerado e por raio — o mesmo cálculo do botão «Calcular "
        "conectividade» na aba «Métricas de paisagem». Mais caro que os "
        "demais: uma segunda consulta ao Earth Engine mais uma busca "
        "geométrica local por conglomerado."
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
    "export_stage_computing_connectivity": "Calculando a conectividade",
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
    "send_dialog_title": "Enviar dados",
    "send_dialog_desc": (
        "Cole uma lista de pontos, cole um polígono em WKT, ou envie um "
        "arquivo KML — para usar no mapa no lugar de clicar."
    ),
    "send_mode_points": "Lista de pontos",
    "send_mode_wkt": "WKT",
    "send_mode_kml": "KML",
    "send_format_label": "Formato: nome (opcional), latitude, longitude",
    "send_max_points": "Até {max} pontos por lista.",
    "send_active_points": "{n} pontos ativos",
    "send_download_all_button": "Baixar todos os pontos juntos",
    "send_truncated": (
        "A lista tem mais de {max} pontos válidos; apenas os primeiros "
        "{max} foram mantidos."
    ),
    "send_wkt_desc": (
        "Cole um polígono ou multipolígono em WKT (ex.: exportado de um "
        "SIG). Substitui a área desenhada/enviada atual, se houver."
    ),
    "send_wkt_placeholder": (
        "POLYGON((-56.0 -12.0, -55.5 -12.0, -55.5 -11.5, -56.0 -11.5, "
        "-56.0 -12.0))"
    ),
    "send_kml_desc": (
        "Envie um arquivo KML com um ou mais polígonos (ex.: exportado do "
        "Google Earth). Apenas Polygon é lido — pontos, linhas, estilos e "
        "outros dados do arquivo são ignorados."
    ),
    "send_kml_dropzone": "Clique ou arraste um arquivo .kml aqui",
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

    # --- region validation (services/region_geometry.py) ------------------- #
    "err_geometry_invalid": "A geometria informada não é válida.",
    "err_geometry_empty": "A geometria informada está vazia.",
    "err_geometry_outside_brazil": (
        "A área informada está fora do Brasil. O MapBiomas cobre apenas o "
        "Brasil, portanto não há histórico de cobertura do solo para esta "
        "região."
    ),
    "err_geometry_too_large": (
        "A área informada ({area_km2:.0f} km²) excede o limite de "
        "{max_km2:.0f} km²."
    ),
    "err_geometry_too_complex": (
        "O contorno tem {n} vértices, acima do limite de {max_n}."
    ),
    "err_wkt_parse": "Não foi possível interpretar o WKT: {exc}",
    "err_wkt_not_polygon": "O WKT precisa descrever um Polygon ou MultiPolygon.",
    "err_kml_too_large": "O arquivo KML excede o limite de {max_mb:.1f} MB.",
    "err_kml_parse": "Não foi possível interpretar o arquivo KML: {exc}",
    "err_kml_no_polygon": "Nenhum polígono foi encontrado no arquivo KML.",

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
