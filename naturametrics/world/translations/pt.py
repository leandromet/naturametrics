"""Portuguese overrides for the world page. Missing keys fall back to English."""

from __future__ import annotations

TRANSLATIONS_PT: dict[str, str] = {
    'nav_toggle_layers_aria': 'Abrir painel de camadas',
    'nav_subtitle': 'Histórico de cobertura do solo, distúrbios e mudança florestal — em qualquer lugar do planeta',
    'nav_title_suffix': 'Mundo',
    'drawer_title': 'Camadas e análise',
    'drawer_close_aria': 'Fechar painel',
    'results_resize_aria': 'Redimensionar o painel de resultados',
    'results_resize_label': 'Redimensionar',
    'results_resize_hint': 'Alterna a altura do painel entre compacto, médio e expandido.',
    'legend_title': 'Legenda',
    'legend_collapse_aria': 'Recolher a legenda',
    'legend_expand_aria': 'Expandir a legenda',
    'go_to_brazil': 'Ir para o Brasil',
    'language_label': 'Idioma',
    'close_button': 'Fechar',
    'search_title': 'Encontrar um lugar',
    'search_placeholder': 'Endereço, coordenada ou lugar…',
    'search_read_as': 'lido como:',
    'search_button': 'Buscar',
    'search_button_busy': 'Buscando…',
    'search_clear_aria': 'Limpar a busca',
    'search_places_heading': 'Lugares e endereços',
    'search_places_note': (
        'Um lugar apenas enquadra o mapa e marca um alfinete. Clique no mapa para '
        'escolher um ponto de análise.'
    ),
    'search_place_hint': 'clique no mapa para escolher um ponto de análise',
    'echo_postal': 'código postal',
    'echo_coordenada': 'coordenada',
    'echo_lugar': 'lugar',
    'erro_postal_nao_encontrado': 'Código postal {code} não encontrado. Tente o endereço.',
    'erro_lugar_nao_encontrado': 'Nenhum lugar encontrado para “{query}”.',
    'precision_endereco': 'endereço',
    'precision_rua': 'rua',
    'precision_cep': 'código postal',
    'precision_bairro': 'bairro',
    'precision_cidade': 'cidade',
    'precision_regiao': 'região',
    'precision_lugar': 'lugar',
    'qs_title': 'Comece em 30 segundos',
    'qs_step1_lead': 'Busque',
    'qs_step1_body': 'um endereço, coordenada ou lugar — ou apenas mova o mapa.',
    'qs_step2_lead': 'Clique em qualquer ponto',
    'qs_step2_body': 'em qualquer ponto do mapa, de 60°S a 85°N: um marcador e cinco áreas de análise são desenhados ao redor.',
    'qs_step3_lead': 'Leia os resultados',
    'qs_step3_body': 'abaixo do mapa: histórico de cobertura do solo (GLC-FCS30D) e perda e ganho florestal.',
    'qs_step4_lead': 'Baixe os dados',
    'qs_step4_body': 'pelo botão «Baixar dados», no topo da página.',
    'qs_more': (
        'Há muito mais: imagens Landsat por ano, camadas de mudança florestal, '
        'prévia das áreas de análise e registros de espécies (GBIF).'
    ),
    'qs_got_it': 'Entendi',
    'qs_full_howto': 'Ver o guia completo',
    'qs_close_aria': 'Fechar o início rápido',
    'help_show_quickstart': 'Mostrar o início rápido de novo',
    'clear_button': 'Limpar',
    'reset_button': 'Restaurar',
    'cancel_button': 'Cancelar',
    'section_point': 'Ponto de estudo',
    'section_basemap': 'Mapa base',
    'section_landcover': 'Cobertura do solo (GLC-FCS30D)',
    'section_buffer_preview': 'Uso no buffer',
    'buffer_preview_toggle_label': 'Ampliar cobertura do solo',
    'buffer_preview_text': 'Mostra o ano mais recente do GLC-FCS30D ({year}) apenas dentro do raio de análise ao redor do ponto clicado, e em nenhum outro lugar. Não faz chamada ao Earth Engine: os tiles já estão carregados e o círculo é um recorte aplicado no navegador.',
    'buffer_preview_hidden_note': 'Redundante enquanto a camada completa do GLC-FCS30D está ligada — a cobertura já está desenhada em todo o mapa.',
    'section_forest_change': 'Mudança florestal (Hansen)',
    'section_landsat': 'Imagens Landsat',
    'year_label': 'Ano',
    'opacity_label': 'Opacidade',
    'forest_change_toggle_label': 'Perda e ganho',
    'change_base_year': 'Perda a partir de',
    'change_loss_label': 'Perda de cobertura arbórea',
    'change_gain_label': 'Ganho de cobertura arbórea',
    'treecover_threshold_label': 'Limiar de floresta (% de dossel em 2000)',
    'forest_change_note': (
        'Hansen Global Forest Change, 2001–2025. O controle de ano filtra apenas a '
        'perda: o ganho é publicado como um único indicador sem data para todo o '
        'período, então o verde não muda ao mover o controle.'
    ),
    'hansen_treecover_toggle': 'Cobertura arbórea 2000',
    'landsat_year_label': 'Ano do composto',
    'landsat_note': (
        'Um composto Landsat sem nuvens por ano, de 1984 a 2026. Desenhado sobre o '
        'mapa base escolhido acima.'
    ),
    'point_click_other': 'Clique no mapa para escolher outro ponto.',
    'point_click_choose': 'Clique no mapa para escolher um ponto.',
    'status_ee_unavailable': 'Earth Engine indisponível',
    'status_ee_connecting': 'Conectando ao Earth Engine…',
    'status_ee_ready': 'Earth Engine pronto',
    'section_gbif': 'Ocorrências de espécies',
    'gbif_toggle_label': 'GBIF — registros de ocorrência',
    'gbif_info': (
        'Registros de ocorrência de espécies do GBIF (Global Biodiversity '
        'Information Facility). Só aparecem a partir do zoom 10 — mais longe que '
        'isso, um ponto individual tem menos de um pixel. A camada mostra no máximo '
        '300 registros por vista; use a busca para restringir o que interessa.'
    ),
    'gbif_zoom_note': 'Aproxime até o zoom 10 ou mais para ver os registros.',
    'gbif_truncated_note': 'registros nesta vista — refine a busca',
    'gbif_taxonomy_group': 'Táxon',
    'gbif_records_group': 'Tipo de registro e ano',
    'gbif_taxonomy_title': 'Navegue pela classificação',
    'gbif_rank_kingdom': 'Reino',
    'gbif_rank_phylum': 'Filo',
    'gbif_rank_class': 'Classe',
    'gbif_rank_order': 'Ordem',
    'gbif_rank_family': 'Família',
    'gbif_rank_genus': 'Gênero',
    'gbif_rank_species': 'Espécie',
    'gbif_name_label': 'Nome científico',
    'gbif_name_placeholder': 'ex.: Ursus arctos, Picea glauca…',
    'gbif_basis_label': 'Base do registro',
    'gbif_year_label': 'Ano do evento',
    'gbif_province_label': 'País',
    'gbif_buffers_run': 'Levantar espécies',
    'gbif_buffers_no_point': 'Escolha um ponto no mapa para levantar as espécies registradas ao redor.',
    'gbif_records_word': 'registros',
    'gbif_species_word': 'espécies',
    'gbif_top_species': 'Espécies mais registradas',
    'gbif_show_zone_hint': 'Mostrar este anel no mapa',
    'landuse_title': 'Histórico de cobertura do solo',
    'analysis_running': 'Processando 17 anos em 5 buffers…',
    'top_classes_title': 'Classes principais ({year})',
    'empty_state_title': 'Clique no mapa para escolher um ponto',
    'empty_state_body': 'O histórico de cobertura do solo (2000–2022) e a mudança florestal de Hansen serão calculados para raios de 0,5, 1, 2, 5 e 10 km ao redor.',
    'change_title': 'Mudança florestal {first}–{last}',
    'change_loss_ha': 'Perda 2001–2025',
    'change_gain_ha': 'Ganho 2000–2012',
    'change_net_ha': 'Saldo 2001–2012',
    'change_gain_undated_note': (
        'O Hansen data a perda ano a ano, mas o ganho é um indicador sem data que '
        'cobre apenas 2000–2012 e “não foi atualizado nas versões seguintes”. Por '
        'isso o ganho é a linha tracejada dentro da faixa sombreada, e não uma '
        'série, e o saldo é de 2001–2012 — os anos que as duas bandas compartilham.'
    ),
    'change_forest2000_ha': 'Floresta em 2000',
    'change_running': 'Lendo perda e ganho do Hansen…',
    'radius_label': 'Raio',
    'gbif_species_tab': 'Espécies (GBIF)',
    'gbif_species_tab_hint': (
        'Espécies já registradas no GBIF dentro de cada buffer do ponto de estudo. '
        'É uma consulta agregada — conta os registros sem baixá-los — e respeita os '
        'mesmos filtros da busca na barra lateral. Os buffers são discos '
        'cumulativos: o de 10 km inclui tudo o que está no de 5 km.'
    ),
    'gbif_buffers_note': 'Discos cumulativos · consulta ao vivo no GBIF',
    'gbif_buffers_empty': 'Nenhum registro neste raio com os filtros atuais.',
    'gbif_col_species': 'Espécie',
    'gbif_col_records': 'Registros',
    'gbif_species_tab_short': 'Espécies',
    'download_button': 'Baixar dados',
    'export_dialog_title': 'Baixar dados',
    'export_dialog_desc': (
        'Uma planilha ODS com uma aba por tabela e uma aba de metadados com a '
        'proveniência completa de cada consulta. Abre no LibreOffice, no Excel e no '
        'Google Planilhas.'
    ),
    'export_point_desc': 'Uma planilha com: a classe GLC-FCS30D do pixel clicado ano a ano, uma aba por raio ({radii} km) com a série completa 2000–2022, perda/ganho de Hansen, o dicionário de classes e uma aba de metadados.',
    'download_point_button': 'Baixar planilha do ponto (.ods)',
    'download_point_hint': 'Clique num ponto do mapa para habilitar.',
    'export_choose_point_first': 'Escolha um ponto no mapa primeiro.',
    'export_stage_building': 'Montando a planilha',
    'export_sheet_failed': 'Falha ao gerar a planilha: {exc}',
    'provenance_callout': (
        'Nenhum número sai daqui sem proveniência: a aba de metadados diz qual '
        'conjunto de dados, quais bandas, qual escala e qual redutor produziram '
        'cada tabela, e traz as atribuições que devem ser citadas.'
    ),
    'no_point_badge': 'nenhum ponto',
    'gbif_export_ods_hint': (
        'Planilha ODS: uma aba de metadados (ponto, filtros, ressalvas e licenças) '
        'e uma aba por raio, com as espécies e seus registros.'
    ),
    'gbif_export_csv_hint': (
        'CSV único com todos os raios (radius_km, espécie, registros, % do raio). '
        'Sem os metadados — as ressalvas da planilha valem igual.'
    ),
    'gbif_export_nothing': 'Levante as espécies antes de exportar.',
    'err_coord_swapped': '{point} está fora da faixa coberta pela página, mas {flipped} está dentro — latitude e longitude parecem trocadas.',
    'err_coord_outside_world': '{point} está fora da faixa coberta pela página (60°S a 85°N).',
    'err_earth_engine_query': 'Falha ao consultar o Earth Engine: {exc}',
    'err_no_landcover': 'Nenhum dado de cobertura do solo neste ponto.',
    'err_forest_failed': 'Falha ao ler os dados de floresta: {exc}',
    'help_trigger': 'Como usar',
    'help_dialog_title': 'Como usar o Naturametrics Mundo',
    'help_dialog_desc': 'Histórico de cobertura do solo, distúrbios e mudança florestal em qualquer ponto de 60°S a 85°N.',
    'help_step1_title': 'Escolha um ponto',
    'help_step1_body': 'Clique em qualquer ponto do mapa entre 60°S e 85°N. Um marcador é criado e cinco áreas de análise (raios de 0,5, 1, 2, 5 e 10 km) são desenhadas ao redor. Cliques feitos nas páginas Brasil, Canadá ou EUA fora do seu país chegam aqui. A página abre no Brasil e na África; use «Mostrar Ásia e Australásia» para carregar o resto dos tiles de cobertura.',
    'help_step2_title': 'Leia o histórico de cobertura do solo',
    'help_step2_body': 'O gráfico abaixo do mapa mostra uma coluna por ano, 2000–2022, nas cores da legenda do GLC-FCS30D. Troque o raio entre 0,5/1/2/5/10 km e use a chave «%» para alternar entre hectares e participação da área.',
    'help_step3_title': 'Atenção às classes',
    'help_step3_body': 'O GLC-FCS30D é um mapa global de cobertura do solo com classificação fina (33 classes); «Lavoura» e «Áreas úmidas» são o que a classificação de satélite enxerga, não registros de uso da terra. É um produto global: menos exato localmente que um mapa nacional. Áreas úmidas e floresta são classes separadas; o gráfico não as une.',
    'help_step4_title': 'Leia a mudança florestal',
    'help_step4_body': (
        'O Hansen Global Forest Change dá a perda de cobertura arbórea ano a ano, '
        'de 2001 a 2025, mais um indicador de ganho. O controle «Limiar de '
        'floresta» define qual porcentagem de dossel em 2000 conta como floresta — '
        'aumente-o para restringir a contagem a povoamentos mais densos.'
    ),
    'help_step5_title': 'Leia os painéis de distúrbio',
    'help_step5_body': 'O histórico de distúrbios mostra a perda de cobertura arbórea a cada ano (Hansen: a causa não é registrada); tempo desde o distúrbio conta os anos desde a última perda detectada em pixels que eram floresta em 2000, limitado a 2001; Fogo mostra a área queimada do MODIS por ano; Dossel mostra a tendência da cobertura arbórea (cobertura de 2000 menos a perda: o rebrote não é contado).',
    'help_step6_title': 'Troque as imagens',
    'help_step6_body': 'A seção GBIF desenha registros de ocorrência a partir do zoom 10 e pode filtrar por nome, classificação, tipo de registro e ano. Com um ponto escolhido, «Espécies nos buffers» lista o que foi registrado em cada raio.',
    'help_step7_title': 'Baixe os dados',
    'help_step7_body': (
        '«Baixar dados» gera uma planilha ODS com todas as tabelas por trás dos '
        'gráficos e uma aba de metadados explicando como cada número foi calculado.'
    ),
    'help_limitations_title': 'Limitações que vale conhecer',
    'help_limit_1': 'O GLC-FCS30D tem um mapa por ano de 2000 a 2022, a 30 m, e a página cobre de 60°S a 85°N. Água aberta não tem classe de terra.',
    'help_limit_2': 'O GLC-FCS30D é uma classificação global de cobertura do solo a 30 m, não um registro de uso ou propriedade da terra, e menos exato localmente que um mapa nacional. Mudanças de classe entre anos consecutivos incluem ruído de classificação.',
    'help_limit_3': (
        'O ganho do Hansen não tem data — é um único indicador para 2000–2012 no '
        'produto original —, então não pode ser filtrado por ano como a perda. A '
        '«perda» do Hansen é qualquer perda de dossel, inclusive fogo e corte, não '
        'só desmatamento.'
    ),
    'help_limit_4': (
        'Resolução de 30 m: num raio de 1 km cabem cerca de 3.500 pixels, então '
        'poucos pixels mal classificados já mexem nas porcentagens.'
    ),
    'cite_trigger': 'Como citar',
    'cite_dialog_title': 'Como citar',
    'cite_dialog_desc': 'Se o Naturametrics Mundo contribuiu para o seu trabalho, cite-o e também os conjuntos de dados usados.',
    'cite_sources_title': 'Bases de dados — cite também',
    'cite_sources_desc': (
        'Cada base tem exigências próprias de atribuição. Ao publicar figuras ou '
        'números obtidos aqui, cite as que foram usadas.'
    ),
    'cite_example_title': 'Exemplo de uso no texto',
    'cite_example_body': '"A área de estudo foi analisada com o Naturametrics (Biondo et al., 2026), usando o GLC-FCS30D (Zhang et al., 2024), o NASA NEX-GDDP-CMIP6 (Thrasher et al., 2022) e o Hansen Global Forest Change (Hansen et al., 2013)."',
    'app_name': 'Naturametrics Mundo — Cobertura do solo, distúrbios e mudança florestal',
    'go_to_canada': 'Canadá',
    'go_to_usa': 'EUA',
    'go_to_world': 'Mundo',
    'start_hint': 'Clique em qualquer ponto do mapa, de 60°S a 85°N, para começar',
    'glc_toggle_label': 'Cobertura do solo GLC-FCS30D',
    'glc_coverage_note': 'O GLC-FCS30D é um mapa global de cobertura do solo a 30 m, um por ano de 2000 a 2022. A página abre com as Américas e Europa–África; Ásia e Australásia carregam sob demanda.',
    'glc_empty': 'Sem cobertura do solo GLC-FCS30D aqui (água aberta, ou fora dos seus tiles). Os painéis de distúrbio, fogo, dossel e mudança florestal ainda respondem onde há terra.',
    'err_extra_failed': 'Falha ao consultar o Earth Engine: {exc}',
    'dist_title': 'Histórico de distúrbios',
    'dist_hint': 'Perda de cobertura arbórea a cada ano (Hansen Global Forest Change). O produto não registra a causa.',
    'dist_empty': 'Nenhuma mudança detectada neste buffer.',
    'dist_attribution': 'Hansen/UMD/Google/USGS/NASA — Global Forest Change v1.13 · 30 m · 2001–2025',
    'age_title': 'Tempo desde o distúrbio',
    'age_hint': 'Área florestal (cobertura em 2000) por anos desde a última perda de cobertura detectada. A última barra é censurada: sem perda desde 2001, não «mais velha que 25 anos».',
    'age_empty': 'Sem cobertura arbórea neste buffer.',
    'age_attribution': 'Derivado do Hansen Global Forest Change (lossyear, treecover2000) · 30 m',
    'age_tree_area': 'Área com árvores',
    'age_tree_share': 'Parte do buffer',
    'age_censored_share': 'Sem perda desde 2001',
    'fire_title': 'Fogo (MODIS)',
    'fire_hint': 'Área queimada por ano do MODIS MCD64A1 (500 m, desde 2001). Mapeia área queimada, não severidade; fogos pequenos escapam entre os pixels.',
    'fire_empty': 'Nenhuma área queimada mapeada pelo MODIS neste buffer.',
    'fire_attribution': 'NASA — MODIS MCD64A1 área queimada, v6.1 · 500 m',
    'canopy_title': 'Dossel arbóreo',
    'canopy_hint': 'Cobertura arbórea média (%) de cada buffer, por ano: a cobertura de 2000 do Hansen menos os pixels perdidos até aquele ano (o rebrote não é contado).',
    'canopy_attribution': 'Hansen/UMD/Google/USGS/NASA — Global Forest Change (treecover2000, lossyear) · 30 m',
    'help_limit_5': 'O tempo desde o distúrbio é derivado, não medido: começa a contar em 2001 e não diz a idade de um povoamento que nunca foi perdido desde então. A área queimada do MODIS (500 m) deixa de ver fogos pequenos; a perda de Hansen não informa a causa.',
    'section_disturbance_layers': 'Distúrbio e fogo',
    'burn_year_note': 'Ano do fogo mais recente visto pelo MODIS, 2001 (claro) a 2025 (escuro).',
    'east_toggle': 'Mostrar Ásia e Australásia',
    'loss_year_toggle': 'Última perda de cobertura arbórea (Hansen)',
    'loss_year_note': 'Ano da perda de cobertura arbórea mais recente, 2001 (amarelo claro) a 2025 (vermelho escuro).',
    'burn_year_toggle': 'Último fogo (MODIS)',
    'group_study_area': 'Ponto de estudo',
    'group_landcover': 'Mapa base e cobertura do solo',
    'group_forest': 'Floresta, dossel e distúrbios',
    'group_biodiversity': 'Biodiversidade (GBIF)',
    'compare_toggle': 'Comparar dois anos',
    'compare_year_left': 'Ano à esquerda (referência)',
    'compare_note': 'Arraste a linha divisória no mapa. O lado direito é o ano escolhido acima; o esquerdo é este ano. Padrão: o ano mais antigo e o mais novo.',
    'extras_running': 'Lendo…',
    'err_extra_failed': 'Falha ao consultar o Earth Engine: {exc}',
    'metrics_title': 'Métricas de paisagem',
    'metrics_hint': 'Manchas, maior mancha, densidade de borda, tamanho efetivo de malha e diversidade das classes em cada raio, no ano de cobertura mais recente.',
    'metrics_none': 'Sem cobertura GLC-FCS30D aqui: sem métricas de paisagem.',
    'biomass_title': 'Biomassa acima do solo',
    'biomass_hint': 'Biomassa média (Mg/ha) por ano para o raio escolhido, com a incerteza do próprio produto.',
    'biomass_none': 'Sem dados de biomassa aqui.',
    'col_radius': 'Raio',
    'col_patches': 'Manchas',
    'col_largest': 'Maior %',
    'col_edge': 'Borda m/ha',
    'col_meff': 'Meff (ha)',
    'col_shannon': 'Shannon',
    'col_evenness': 'Equitabilidade',
    'col_year': 'Ano',
    'col_mgha': 'Mg/ha',
    'col_sd': '± (produto)',
    'biomass_attr': 'ESA CCI Biomass v6.0 — Santoro & Cartus (2025) · 100 m',
    'tab_dist': 'Distúrbios',
    'tab_age': 'Tempo desde distúrbio',
    'tab_fire': 'Fogo',
    'tab_canopy': 'Dossel',
    'tab_climate': 'Clima',
    'climate_title': 'Clima, perigo de fogo e relevo',
    'climate_hint': 'Mediana de nove modelos CMIP6 para a célula do ponto, em dois cenários de emissões, com a classe Köppen-Geiger e o relevo ao redor do ponto.',
    'tab_forest': 'Mudança florestal',
    'tab_metrics': 'Paisagem',
    'tab_biomass': 'Biomassa',
    'tab_species': 'Espécies (GBIF)',
    'metrics_attr': 'GLC-FCS30D 2022 · 30 m',
}
