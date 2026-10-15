"""The report's words: titles, captions, headers and explanatory sentences.

Deterministic templates, one dict per language (doc/14 §2.8, decision R6):
Portuguese is the reference and English falls back to it key by key, the same
rule as ``translations/``. Every number in a sentence is formatted through
``report_kit.text`` so a Portuguese report reads "1.234,5 ha" and an English
one "1,234.5 ha", and every number comes from the frame the section's chart or
table was drawn from — nothing here queries or recomputes anything.

**Describe, never judge.** The sentences state quantities, changes over the
period and comparisons between buffers. No causes ("because of…"), no legal,
compliance or valuation vocabulary. The vegetation-age sentence always states
the censored share (constraint C5), and a multi-selection ``sum`` always
carries the overlap caveat.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import pandas as pd

from ..config import mapbiomas as mb
from ..config import vegetation_age as fa
from ..report_kit.text import fmt_ha, fmt_int, fmt_num, fmt_pct, fmt_signed

PERIOD = f"{mb.MAPBIOMAS_YEAR_START}–{mb.MAPBIOMAS_YEAR_END}"

_PT: dict[str, str] = {
    # --- document ---------------------------------------------------------- #
    "title": "Relatório de local",
    "title_selection": "Relatório de seleção",
    "subject_selection_sum": "Seleção de {n} conglomerado(s) — soma dos buffers",
    "subject_selection_full": "Seleção de {n} conglomerado(s) — área total",
    # --- sections ------------------------------------------------------------ #
    "sec_identification": "Identificação",
    "sec_about": "Sobre este relatório",
    "sec_maps": "Mapas",
    "sec_land_cover": "Uso e cobertura da terra",
    "sec_pixel": "O pixel do ponto",
    "sec_age": "Idade da vegetação nativa",
    "sec_change": "Mudança desde 2008",
    "sec_biomass": "Biomassa acima do solo",
    "sec_landscape": "Métricas de paisagem",
    "sec_connectivity": "Conectividade entre fragmentos",
    "sec_ibge": "IBGE × MapBiomas",
    "sec_gbif": "Ocorrências de espécies (GBIF)",
    "sec_per_point": "Por conglomerado",
    "sec_provenance": "Métodos e proveniência",
    "sec_sources": "Fontes, citação e atribuições",
    "sec_appendix": "Apêndice",
    # --- contents reasons --------------------------------------------------- #
    "reason_unticked": "desmarcado na janela de exportação",
    "reason_no_result": "sem resultado na tela",
    "reason_failed": "a consulta falhou: {error}",
    "reason_not_for_selection": "não é calculado para uma seleção",
    "reason_connectivity_button": "calculado só pelo botão próprio na aba de paisagem",
    "reason_gbif_run": "levante as espécies na aba GBIF antes de exportar",
    "reason_maps_failed": "nenhum mapa pôde ser obtido: {error}",
    "reason_point_only": "só existe para um ponto de estudo",
    "reason_maps_offline": "os mapas não foram obtidos do Earth Engine",
    # --- identification ----------------------------------------------------- #
    "kv_coordinates": "Coordenadas",
    "kv_dms": "Coordenadas (GMS)",
    "kv_origin": "Origem",
    "kv_origin_click": "clique no mapa",
    "kv_origin_conglomerado": "conglomerado {c} (IFN)",
    "kv_uf": "UF",
    "kv_municipio": "Município",
    "kv_bioma": "Bioma",
    "kv_buffers": "Buffers",
    "kv_buffers_value": "{radii} ({shape})",
    "shape_circle": "círculos concêntricos, discos completos",
    "shape_square": "quadrados concêntricos, lado = 2 × raio",
    "kv_period": "Período",
    "kv_analysis_time": "Análise calculada em",
    "kv_n_points": "Conglomerados",
    "kv_view_mode": "Modo de visualização",
    "view_sum": "soma dos buffers de cada conglomerado",
    "view_full_area": "área total (retângulo que envolve os buffers)",
    "locator_caption": "Localização no Brasil.",
    "locator_caption_selection": "Extensão da seleção no Brasil.",
    "points_caption": "Conglomerados da seleção.",
    "h_conglomerado": "Conglomerado",
    "h_place": "Município · UF",
    "h_bioma": "Bioma",
    "h_lat": "Latitude",
    "h_lon": "Longitude",
    # --- about -------------------------------------------------------------- #
    "about_point": (
        "Este relatório descreve o entorno de um ponto de estudo com dados de "
        "{period}, em buffers de {radii} ({shape}). As figuras mostram o buffer "
        "de {active}, o selecionado na tela; as tabelas cobrem todos os buffers. "
        "Os números são os mesmos da análise exibida na tela, sem novo cálculo. "
        "Leia-o como **dados, não como um veredito**: ele descreve o que as bases "
        "mostram, sem atribuir causas nem avaliar situação legal."),
    "about_selection": (
        "Este relatório descreve uma seleção de {n} conglomerado(s) com dados de "
        "{period}, em buffers de {radii} ({mode}). As figuras mostram o buffer de "
        "{active}; as tabelas cobrem todos os buffers presentes. Os números são "
        "os mesmos da análise exibida na tela, sem novo cálculo. Leia-o como "
        "**dados, não como um veredito**: ele descreve o que as bases mostram, "
        "sem atribuir causas nem avaliar situação legal."),
    "overlap_caveat": (
        "Os totais somam os buffers de cada conglomerado; onde eles se "
        "sobrepõem, a mesma área é contada uma vez por conglomerado, portanto o "
        "total não é a área da união."),
    "overlap_title": "Sobreposição",
    # --- maps --------------------------------------------------------------- #
    "map_imagery_caption": "Imagem de satélite do entorno com os buffers de {radii}.",
    "map_mapbiomas_caption": "Uso e cobertura da terra em {year} (MapBiomas Coleção 11) com os buffers.",
    "map_mapbiomas_caption_selection": "Uso e cobertura da terra em {year} (MapBiomas Coleção 11) com os conglomerados e seus buffers de {radius}.",
    "map_change_caption": "Mudança da vegetação natural entre {y0} e {y1} (MapBiomas) com os buffers.",
    "map_unavailable": "Mapa indisponível: {error}",
    "legend_point": "Ponto de estudo",
    "legend_points": "Conglomerados",
    "legend_buffers": "Buffers ({radii})",
    "legend_full_area": "Área total",
    "legend_other_classes": "outras classes",
    # --- intros ------------------------------------------------------------- #
    "intro_land_cover": (
        "O MapBiomas classifica cada pixel de 30 m do Brasil em uma classe de "
        "uso e cobertura, a cada ano de {period}; a figura empilha a área de "
        "cada classe dentro do buffer, ano a ano."),
    "intro_pixel": (
        "A série de classes do pixel de 30 m exatamente sob o ponto, agrupada em "
        "períodos contínuos da mesma classe."),
    "intro_age": (
        "A idade estima há quantos anos cada pixel é vegetação nativa sem "
        "interrupção detectada (MapBiomas Desmatamento e Vegetação Secundária). "
        "Pixels sem mudança em todo o registro têm idade **censurada**: sabe-se "
        "apenas que é de pelo menos {c} anos."),
    "intro_change": (
        "Compara a vegetação natural (MapBiomas) de {y0}, ano de referência do "
        "Código Florestal, com a de {y1}: área que deixou de ser vegetação "
        "natural, área que voltou a sê-lo e área estável."),
    "intro_biomass": (
        "Biomassa acima do solo média, em megagramas por hectare, do ESA CCI "
        "Biomass v6.0 — dez anos disponíveis entre 2007 e 2022."),
    "intro_landscape": (
        "Métricas de paisagem calculadas sobre o mapa MapBiomas mais recente: "
        "manchas contíguas da mesma classe, borda entre classes e diversidade."),
    "intro_connectivity": (
        "Distância de cada fragmento de floresta ao vizinho mais próximo (ENN), "
        "calculada sob demanda."),
    "intro_ibge": (
        "Compara, no mesmo buffer, o mapa de vegetação do IBGE (2022) com o "
        "MapBiomas de 2022, reduzidos a seis grupos comuns; cada célula é a "
        "porcentagem da área com aquela combinação."),
    "intro_gbif": (
        "Registros de ocorrência de espécies do GBIF dentro de cada buffer, com "
        "os filtros ativos no momento do levantamento. Registros refletem onde "
        "houve coleta, não a distribuição completa das espécies."),
    "intro_per_point": (
        "Participação da vegetação natural em cada conglomerado da seleção, no "
        "buffer de {radius}, no primeiro e no último ano."),
    # --- figure captions ---------------------------------------------------- #
    "cap_land_cover": "Uso e cobertura da terra, {period}, buffer de {radius}.",
    "cap_age_point": "Idade da vegetação no pixel do ponto, ano a ano.",
    "cap_age_hist": "Área de vegetação nativa por classe de idade, buffer de {radius}.",
    "cap_change": "Perda e regeneração de vegetação natural, {y0}–{y1}, buffer de {radius}.",
    "cap_biomass": "Biomassa acima do solo (ESA CCI), buffer de {radius}.",
    "cap_ibge": "IBGE Vegetação 2022 × MapBiomas 2022, buffer de {radius} (% da área).",
    "fig_not_rendered": "o navegador não devolveu a imagem ({error})",
    # --- table captions / headers ------------------------------------------ #
    "tab_natural_by_radius": "Vegetação natural por buffer, {y0} e {y1}.",
    "tab_classes": "Área por classe no buffer de {radius}, {y0} e {y1}.",
    "tab_pixel_runs": "Classes do pixel do ponto, por período.",
    "tab_age": "Resumo da idade da vegetação nativa por buffer.",
    "tab_change": "Mudança da vegetação natural por buffer, {y0}–{y1}.",
    "tab_biomass": "Biomassa acima do solo média (Mg/ha) por ano e buffer.",
    "tab_landscape": "Métricas de paisagem por buffer.",
    "tab_connectivity": "Conectividade entre fragmentos de floresta por buffer.",
    "tab_ibge": "Floresta e vegetação natural segundo cada fonte, por buffer (% da área).",
    "tab_gbif": "Registros e espécies do GBIF por buffer.",
    "tab_gbif_species": "Espécies com mais registros no buffer de {radius}.",
    "tab_per_point": "Vegetação natural por conglomerado, buffer de {radius}.",
    "tab_app_classes": "Área por classe e buffer, {y0} e {y1}.",
    "tab_app_age": "Área por idade e buffer.",
    "h_buffer": "Buffer",
    "h_class": "Classe",
    "h_area_y": "Área {y} (ha)",
    "h_pct_y": "% {y}",
    "h_change_ha": "Variação (ha)",
    "h_change_pct": "Variação (%)",
    "h_natural_y": "Veg. natural {y} (ha)",
    "h_years": "Anos",
    "h_n_years": "Nº de anos",
    "h_total_natural": "Veg. nativa (ha)",
    "h_median_age": "Idade mediana datada (anos)",
    "h_censored_pct": "Censurada (%)",
    "h_censored_ha": "Censurada (ha)",
    "h_loss": "Perda (ha)",
    "h_gain": "Regeneração (ha)",
    "h_stable": "Estável (ha)",
    "h_year": "Ano",
    "h_area_ha": "Área (ha)",
    "h_patches": "Manchas",
    "h_patch_density": "Manchas/ha",
    "h_largest_pct": "Maior mancha (%)",
    "h_edge_density": "Borda (m/ha)",
    "h_meff": "Meff (ha)",
    "h_shannon": "Shannon",
    "h_evenness": "Equidade",
    "h_fragments": "Fragmentos",
    "h_enn_mean": "ENN média (m)",
    "h_enn_median": "ENN mediana (m)",
    "h_forest_ibge": "Floresta IBGE",
    "h_forest_mb": "Floresta MapBiomas",
    "h_natural_ibge": "Natural IBGE",
    "h_natural_mb": "Natural MapBiomas",
    "h_records": "Registros",
    "h_richness": "Espécies",
    "h_species": "Espécie",
    "h_age": "Idade (anos)",
    "h_censored": "Censurada",
    "yes": "sim",
    "no": "não",
    "pixel_caveat": (
        "Valores de UM pixel de 30 m. Um único pixel é ruidoso: um ano mal "
        "classificado aparece como uma transição que não existiu. Para tendência, "
        "use os buffers, que agregam milhares de pixels."),
    "pixel_caveat_title": "Um pixel",
    "biomass_no_sd": "Na soma de vários conglomerados o desvio-padrão não é combinável e não é mostrado.",
    # --- reading sentences --------------------------------------------------- #
    "scope_point": "No buffer de {radius}",
    "scope_sum": "Na soma dos buffers de {radius} dos {n} conglomerados",
    "scope_full": "Na área total que envolve os buffers de {radius}",
    "lc_sentence": (
        "{scope}, **{cls}** ocupava {a0} ({p0}) em {y0} e {a1} ({p1}) em {y1}, "
        "{delta}."),
    "lc_decrease": "uma redução de {v}",
    "lc_increase": "um aumento de {v}",
    "lc_same": "sem variação",
    "lc_grew": " A classe que mais cresceu foi **{cls}** ({v}).",
    "lc_empty": "Não há histórico de uso da terra para este buffer.",
    "natural_sentence": (
        "A vegetação natural somava {a0} ({p0}) em {y0} e {a1} ({p1}) em {y1}."),
    "pixel_sentence": (
        "Entre {y0} e {y1}, o pixel do ponto passou por {n} período(s) de "
        "classe; em {y1} ele é **{cls}**."),
    "age_sentence": (
        "{scope}, metade da vegetação nativa com idade datada tem até {median} "
        "anos; {cpct} da vegetação nativa ({cha}) está no limite da série "
        "(idade censurada: pelo menos {c} anos)."),
    "age_sentence_all_censored": (
        "{scope}, nenhuma área de vegetação nativa tem idade datada; {cpct} dela "
        "({cha}) está no limite da série (idade censurada: pelo menos {c} anos)."),
    "age_point_sentence": "No pixel do ponto, a idade da vegetação em {y} é de {age} anos.",
    "age_point_censored": (
        "No pixel do ponto, a vegetação está no limite da série em {y} (idade "
        "censurada: pelo menos {c} anos)."),
    "age_point_zero": "No pixel do ponto, não há vegetação nativa em {y} (idade 0).",
    "change_sentence": (
        "Desde {y0}, {loss} deixaram de ser vegetação natural no buffer de "
        "{radius} e {gain} voltaram a sê-lo; {stable} permaneceram vegetação "
        "natural."),
    "biomass_sentence": (
        "{scope}, a biomassa acima do solo média foi de {b0} Mg/ha em {y0} e de "
        "{b1} Mg/ha em {y1} ({d} Mg/ha)."),
    "landscape_sentence": (
        "{scope}, o mapa tem {patches} manchas (de todas as classes); a maior "
        "ocupa {lpi} da área, e a densidade de borda é de {ed} m/ha."),
    "connectivity_sentence": (
        "No buffer de {radius}, {n} fragmentos de floresta estão, em mediana, a "
        "{median} m do vizinho mais próximo."),
    "ibge_sentence": (
        "{scope}, o IBGE classifica {fi} da área como floresta e o MapBiomas, "
        "{fm}; como vegetação natural, {ni} e {nm}, respectivamente."),
    "gbif_sentence": (
        "No buffer de {radius}, o GBIF tem {total} registros de ocorrência de "
        "{richness} espécies."),
    "per_point_sentence": (
        "Entre os {n} conglomerados, a participação da vegetação natural no "
        "buffer de {radius} em {y1} vai de {lo} a {hi}."),
    # --- citation ------------------------------------------------------------ #
    "citation_note": "Ao publicar, cite o aplicativo e também as bases de dados usadas, listadas abaixo.",
}

_EN: dict[str, str] = {
    "title": "Site report",
    "title_selection": "Selection report",
    "subject_selection_sum": "Selection of {n} conglomerado(s) — sum of buffers",
    "subject_selection_full": "Selection of {n} conglomerado(s) — full area",
    "sec_identification": "Identification",
    "sec_about": "About this report",
    "sec_maps": "Maps",
    "sec_land_cover": "Land use and cover",
    "sec_pixel": "The point's own pixel",
    "sec_age": "Native vegetation age",
    "sec_change": "Change since 2008",
    "sec_biomass": "Above-ground biomass",
    "sec_landscape": "Landscape metrics",
    "sec_connectivity": "Fragment connectivity",
    "sec_ibge": "IBGE × MapBiomas",
    "sec_gbif": "Species occurrences (GBIF)",
    "sec_per_point": "Per conglomerado",
    "sec_provenance": "Methods and provenance",
    "sec_sources": "Sources, citation and attributions",
    "sec_appendix": "Appendix",
    "reason_unticked": "unticked in the export dialog",
    "reason_no_result": "no result on screen",
    "reason_failed": "the query failed: {error}",
    "reason_not_for_selection": "not computed for a selection",
    "reason_connectivity_button": "computed only by its own button in the landscape tab",
    "reason_gbif_run": "survey the species in the GBIF tab before exporting",
    "reason_maps_failed": "no map could be fetched: {error}",
    "reason_point_only": "exists only for a study point",
    "reason_maps_offline": "the maps were not fetched from Earth Engine",
    "kv_coordinates": "Coordinates",
    "kv_dms": "Coordinates (DMS)",
    "kv_origin": "Origin",
    "kv_origin_click": "map click",
    "kv_origin_conglomerado": "conglomerado {c} (National Forest Inventory)",
    "kv_uf": "State",
    "kv_municipio": "Municipality",
    "kv_bioma": "Biome",
    "kv_buffers": "Buffers",
    "kv_buffers_value": "{radii} ({shape})",
    "shape_circle": "concentric circles, full discs",
    "shape_square": "concentric squares, side = 2 × radius",
    "kv_period": "Period",
    "kv_analysis_time": "Analysis computed",
    "kv_n_points": "Conglomerados",
    "kv_view_mode": "View mode",
    "view_sum": "sum of each conglomerado's buffers",
    "view_full_area": "full area (the rectangle enclosing the buffers)",
    "locator_caption": "Location in Brazil.",
    "locator_caption_selection": "Extent of the selection in Brazil.",
    "points_caption": "Conglomerados in the selection.",
    "h_conglomerado": "Conglomerado",
    "h_place": "Municipality · State",
    "h_bioma": "Biome",
    "h_lat": "Latitude",
    "h_lon": "Longitude",
    "about_point": (
        "This report describes the surroundings of a study point with data for "
        "{period}, in {radii} buffers ({shape}). Figures show the {active} "
        "buffer, the one selected on screen; tables cover every buffer. The "
        "numbers are those of the analysis shown on screen, not recomputed. Read "
        "it as **data, not a verdict**: it describes what the datasets show, "
        "without attributing causes or assessing legal status."),
    "about_selection": (
        "This report describes a selection of {n} conglomerado(s) with data for "
        "{period}, in {radii} buffers ({mode}). Figures show the {active} "
        "buffer; tables cover every buffer present. The numbers are those of the "
        "analysis shown on screen, not recomputed. Read it as **data, not a "
        "verdict**: it describes what the datasets show, without attributing "
        "causes or assessing legal status."),
    "overlap_caveat": (
        "Totals add up each conglomerado's buffers; where they overlap the same "
        "ground is counted once per conglomerado, so the total is not the area "
        "of their union."),
    "overlap_title": "Overlap",
    "map_imagery_caption": "Satellite image of the surroundings with the {radii} buffers.",
    "map_mapbiomas_caption": "Land use and cover in {year} (MapBiomas Collection 11) with the buffers.",
    "map_mapbiomas_caption_selection": "Land use and cover in {year} (MapBiomas Collection 11) with the conglomerados and their {radius} buffers.",
    "map_change_caption": "Natural-vegetation change between {y0} and {y1} (MapBiomas) with the buffers.",
    "map_unavailable": "Map unavailable: {error}",
    "legend_point": "Study point",
    "legend_points": "Conglomerados",
    "legend_buffers": "Buffers ({radii})",
    "legend_full_area": "Full area",
    "legend_other_classes": "other classes",
    "intro_land_cover": (
        "MapBiomas assigns every 30 m pixel in Brazil to a land use and cover "
        "class for each year of {period}; the figure stacks each class's area "
        "inside the buffer, year by year."),
    "intro_pixel": (
        "The class series of the 30 m pixel directly under the point, grouped "
        "into continuous runs of the same class."),
    "intro_age": (
        "Age estimates for how many years each pixel has been native vegetation "
        "without a detected interruption (MapBiomas Deforestation and Secondary "
        "Vegetation). Pixels with no change over the whole record have a "
        "**censored** age: it is only known to be at least {c} years."),
    "intro_change": (
        "Compares natural vegetation (MapBiomas) in {y0}, the Forest Code "
        "reference year, with {y1}: area that stopped being natural vegetation, "
        "area that became natural again and stable area."),
    "intro_biomass": (
        "Mean above-ground biomass, in megagrams per hectare, from ESA CCI "
        "Biomass v6.0 — ten years available between 2007 and 2022."),
    "intro_landscape": (
        "Landscape metrics computed on the latest MapBiomas map: contiguous "
        "patches of the same class, edge between classes and diversity."),
    "intro_connectivity": (
        "Distance from each forest fragment to its nearest neighbour (ENN), "
        "computed on demand."),
    "intro_ibge": (
        "Compares, in the same buffer, IBGE's vegetation map (2022) with "
        "MapBiomas 2022, both reduced to six shared groups; each cell is the "
        "percentage of the area with that combination."),
    "intro_gbif": (
        "GBIF species occurrence records inside each buffer, with the filters "
        "active when the survey ran. Records reflect where collecting happened, "
        "not the species' full distribution."),
    "intro_per_point": (
        "Share of natural vegetation in each conglomerado of the selection, in "
        "the {radius} buffer, in the first and the last year."),
    "cap_land_cover": "Land use and cover, {period}, {radius} buffer.",
    "cap_age_point": "Vegetation age at the point's pixel, year by year.",
    "cap_age_hist": "Native vegetation area by age class, {radius} buffer.",
    "cap_change": "Natural-vegetation loss and regrowth, {y0}–{y1}, {radius} buffer.",
    "cap_biomass": "Above-ground biomass (ESA CCI), {radius} buffer.",
    "cap_ibge": "IBGE Vegetation 2022 × MapBiomas 2022, {radius} buffer (% of area).",
    "fig_not_rendered": "the browser did not return the image ({error})",
    "tab_natural_by_radius": "Natural vegetation per buffer, {y0} and {y1}.",
    "tab_classes": "Area by class in the {radius} buffer, {y0} and {y1}.",
    "tab_pixel_runs": "Classes of the point's pixel, by run.",
    "tab_age": "Native vegetation age summary per buffer.",
    "tab_change": "Natural-vegetation change per buffer, {y0}–{y1}.",
    "tab_biomass": "Mean above-ground biomass (Mg/ha) per year and buffer.",
    "tab_landscape": "Landscape metrics per buffer.",
    "tab_connectivity": "Forest-fragment connectivity per buffer.",
    "tab_ibge": "Forest and natural vegetation according to each source, per buffer (% of area).",
    "tab_gbif": "GBIF records and species per buffer.",
    "tab_gbif_species": "Species with the most records in the {radius} buffer.",
    "tab_per_point": "Natural vegetation per conglomerado, {radius} buffer.",
    "tab_app_classes": "Area by class and buffer, {y0} and {y1}.",
    "tab_app_age": "Area by age and buffer.",
    "h_buffer": "Buffer",
    "h_class": "Class",
    "h_area_y": "Area {y} (ha)",
    "h_pct_y": "% {y}",
    "h_change_ha": "Change (ha)",
    "h_change_pct": "Change (%)",
    "h_natural_y": "Natural veg. {y} (ha)",
    "h_years": "Years",
    "h_n_years": "No. of years",
    "h_total_natural": "Native veg. (ha)",
    "h_median_age": "Median dated age (years)",
    "h_censored_pct": "Censored (%)",
    "h_censored_ha": "Censored (ha)",
    "h_loss": "Loss (ha)",
    "h_gain": "Regrowth (ha)",
    "h_stable": "Stable (ha)",
    "h_year": "Year",
    "h_area_ha": "Area (ha)",
    "h_patches": "Patches",
    "h_patch_density": "Patches/ha",
    "h_largest_pct": "Largest patch (%)",
    "h_edge_density": "Edge (m/ha)",
    "h_meff": "Meff (ha)",
    "h_shannon": "Shannon",
    "h_evenness": "Evenness",
    "h_fragments": "Fragments",
    "h_enn_mean": "Mean ENN (m)",
    "h_enn_median": "Median ENN (m)",
    "h_forest_ibge": "Forest IBGE",
    "h_forest_mb": "Forest MapBiomas",
    "h_natural_ibge": "Natural IBGE",
    "h_natural_mb": "Natural MapBiomas",
    "h_records": "Records",
    "h_richness": "Species",
    "h_species": "Species",
    "h_age": "Age (years)",
    "h_censored": "Censored",
    "yes": "yes",
    "no": "no",
    "pixel_caveat": (
        "Values of ONE 30 m pixel. A single pixel is noisy: one misclassified "
        "year shows up as a transition that never happened. For trends, use the "
        "buffers, which aggregate thousands of pixels."),
    "pixel_caveat_title": "One pixel",
    "biomass_no_sd": "Summed over several conglomerados the standard deviation cannot be combined and is not shown.",
    "scope_point": "Within the {radius} buffer",
    "scope_sum": "Summed over the {n} conglomerados' {radius} buffers",
    "scope_full": "Over the full area enclosing the {radius} buffers",
    "lc_sentence": (
        "{scope}, **{cls}** covered {a0} ({p0}) in {y0} and {a1} ({p1}) in {y1}, "
        "{delta}."),
    "lc_decrease": "a decrease of {v}",
    "lc_increase": "an increase of {v}",
    "lc_same": "unchanged",
    "lc_grew": " The class that grew most was **{cls}** ({v}).",
    "lc_empty": "There is no land-use history for this buffer.",
    "natural_sentence": (
        "Natural vegetation added up to {a0} ({p0}) in {y0} and {a1} ({p1}) in {y1}."),
    "pixel_sentence": (
        "Between {y0} and {y1}, the point's pixel went through {n} class run(s); "
        "in {y1} it is **{cls}**."),
    "age_sentence": (
        "{scope}, half of the native vegetation with a dated age is {median} "
        "years old or younger; {cpct} of the native vegetation ({cha}) sits at "
        "the series limit (censored age: at least {c} years)."),
    "age_sentence_all_censored": (
        "{scope}, no native vegetation has a dated age; {cpct} of it ({cha}) "
        "sits at the series limit (censored age: at least {c} years)."),
    "age_point_sentence": "At the point's pixel, the vegetation age in {y} is {age} years.",
    "age_point_censored": (
        "At the point's pixel, the vegetation sits at the series limit in {y} "
        "(censored age: at least {c} years)."),
    "age_point_zero": "At the point's pixel, there is no native vegetation in {y} (age 0).",
    "change_sentence": (
        "Since {y0}, {loss} within the {radius} buffer stopped being natural "
        "vegetation and {gain} became natural again; {stable} remained natural "
        "vegetation."),
    "biomass_sentence": (
        "{scope}, mean above-ground biomass was {b0} Mg/ha in {y0} and {b1} "
        "Mg/ha in {y1} ({d} Mg/ha)."),
    "landscape_sentence": (
        "{scope}, the map has {patches} patches (all classes); the largest "
        "covers {lpi} of the area, and edge density is {ed} m/ha."),
    "connectivity_sentence": (
        "Within the {radius} buffer, {n} forest fragments lie a median of "
        "{median} m from their nearest neighbour."),
    "ibge_sentence": (
        "{scope}, IBGE classifies {fi} of the area as forest and MapBiomas "
        "{fm}; as natural vegetation, {ni} and {nm} respectively."),
    "gbif_sentence": (
        "Within the {radius} buffer, GBIF holds {total} occurrence records of "
        "{richness} species."),
    "per_point_sentence": (
        "Across the {n} conglomerados, the share of natural vegetation in the "
        "{radius} buffer in {y1} ranges from {lo} to {hi}."),
    "citation_note": "When publishing, cite the app and also the datasets used, listed below.",
}

TEMPLATES: dict[str, dict[str, str]] = {"pt": _PT, "en": _EN}


def tx(key: str, lang: str = "pt", **kw: Any) -> str:
    """A report string in ``lang``; Portuguese when the language (or the key
    in it) is missing. Placeholders are filled here, in Python."""
    table = TEMPLATES.get(lang) or _PT
    text = table.get(key, _PT[key])
    return text.format(**kw) if kw else text


def text_lang(lang: str) -> str:
    """The language the numbers are formatted in — the template language."""
    return lang if lang in TEMPLATES else "pt"


# --------------------------------------------------------------------------- #
# Small formatting helpers
# --------------------------------------------------------------------------- #

def radius_label(r: float, shape: str = "circle", lang: str = "pt") -> str:
    """The buffer as the screen labels it: a square's side is twice its
    radius key (state/_analysis.py::_radius_label)."""
    value = 2 * r if shape == "square" else r
    return f"{fmt_num(value, 1 if value % 1 else 0, lang)} km"


def radii_label(radii: Sequence[float], shape: str = "circle", lang: str = "pt") -> str:
    vals = [2 * r if shape == "square" else r for r in radii]
    sep = "; " if lang == "pt" else ", "
    return sep.join(fmt_num(v, 1 if v % 1 else 0, lang) for v in vals) + " km"


def dms(lat: float, lon: float) -> str:
    def one(v: float, pos: str, neg: str) -> str:
        hemi = pos if v >= 0 else neg
        v = abs(v)
        d = int(v)
        m_float = (v - d) * 60
        m = int(m_float)
        s = (m_float - m) * 60
        if round(s, 1) >= 60:
            s, m = 0.0, m + 1
        if m >= 60:
            m, d = 0, d + 1
        return f"{d}°{m:02d}′{s:04.1f}″ {hemi}"
    return f"{one(lat, 'N', 'S')}, {one(lon, 'E', 'W')}"


def scope_phrase(scope: str, radius: float, lang: str, n: int = 0,
                 shape: str = "circle") -> str:
    """How a sentence opens: one point's buffer, a selection's summed
    buffers, or the full-area rectangle."""
    rl = radius_label(radius, shape, lang)
    key = {"sum": "scope_sum", "full_area": "scope_full"}.get(scope, "scope_point")
    return tx(key, lang, radius=rl, n=n)


def _at(df: Optional[pd.DataFrame], radius: float) -> pd.DataFrame:
    if df is None or df.empty or "radius_km" not in df.columns:
        return pd.DataFrame()
    return df[df["radius_km"].astype(float) == float(radius)]


# --------------------------------------------------------------------------- #
# Reading sentences — one per section, each from that section's own frame
# --------------------------------------------------------------------------- #

def land_cover_sentence(history: pd.DataFrame, radius: float, lang: str = "pt",
                        scope: str = "point", n: int = 0,
                        shape: str = "circle") -> str:
    """The largest natural class (or, failing that, the largest class) in the
    first year, followed to the last year; then the class that grew most."""
    L = text_lang(lang)
    sub = _at(history, radius)
    if sub.empty:
        return tx("lc_empty", L)
    y0, y1 = int(sub["year"].min()), int(sub["year"].max())
    by = sub.groupby(["year", "class_id"])["area_ha"].sum()
    first = by.xs(y0, level="year")
    last = by.xs(y1, level="year")
    tot0, tot1 = float(first.sum()) or 1.0, float(last.sum()) or 1.0
    natural = [c for c in first.index if int(c) in mb.NATURAL_VEGETATION and first[c] > 0]
    pool = natural or [c for c in first.index if first[c] > 0] or list(first.index)
    cls = max(pool, key=lambda c: first[c])
    a0, a1 = float(first.get(cls, 0.0)), float(last.get(cls, 0.0))
    diff = a1 - a0
    if abs(diff) < 0.05:
        delta = tx("lc_same", L)
    elif diff < 0:
        delta = tx("lc_decrease", L, v=fmt_ha(-diff, 0, L))
    else:
        delta = tx("lc_increase", L, v=fmt_ha(diff, 0, L))
    text = tx("lc_sentence", L,
              scope=scope_phrase(scope, radius, L, n, shape),
              cls=mb.label(int(cls), L), a0=fmt_ha(a0, 0, L),
              p0=fmt_pct(a0 / tot0 * 100, 1, L), y0=y0, a1=fmt_ha(a1, 0, L),
              p1=fmt_pct(a1 / tot1 * 100, 1, L), y1=y1, delta=delta)
    change = last.reindex(last.index.union(first.index), fill_value=0.0) - \
        first.reindex(last.index.union(first.index), fill_value=0.0)
    change = change.drop(labels=[cls], errors="ignore")
    if not change.empty and float(change.max()) >= 0.5:
        grew = change.idxmax()
        text += tx("lc_grew", L, cls=mb.label(int(grew), L),
                   v=fmt_signed(float(change.max()), 0, L) + " ha")
    return text


def natural_sentence(history: pd.DataFrame, radius: float, lang: str = "pt") -> str:
    L = text_lang(lang)
    sub = _at(history, radius)
    if sub.empty:
        return ""
    y0, y1 = int(sub["year"].min()), int(sub["year"].max())
    nat = sub["class_id"].astype(int).isin(mb.NATURAL_VEGETATION)
    tot = sub.groupby("year")["area_ha"].sum()
    natv = sub[nat].groupby("year")["area_ha"].sum()
    a0, a1 = float(natv.get(y0, 0.0)), float(natv.get(y1, 0.0))
    t0, t1 = float(tot.get(y0, 0.0)) or 1.0, float(tot.get(y1, 0.0)) or 1.0
    return tx("natural_sentence", L, a0=fmt_ha(a0, 0, L), p0=fmt_pct(a0 / t0 * 100, 1, L),
              y0=y0, a1=fmt_ha(a1, 0, L), p1=fmt_pct(a1 / t1 * 100, 1, L), y1=y1)


def pixel_runs(pixel: pd.DataFrame, lang: str = "pt") -> list[tuple[int, int, str]]:
    """``(year_from, year_to, class label)`` runs of the point's pixel."""
    if pixel is None or pixel.empty or "year" not in pixel.columns:
        return []
    col = "class_pt" if text_lang(lang) == "pt" else "class_en"
    if col not in pixel.columns:
        col = "class_pt"
    runs: list[tuple[int, int, str]] = []
    for _, row in pixel.sort_values("year").iterrows():
        label = str(row.get(col, ""))
        year = int(row["year"])
        if runs and runs[-1][2] == label and runs[-1][1] == year - 1:
            runs[-1] = (runs[-1][0], year, label)
        else:
            runs.append((year, year, label))
    return runs


def pixel_sentence(pixel: pd.DataFrame, lang: str = "pt") -> str:
    L = text_lang(lang)
    runs = pixel_runs(pixel, L)
    if not runs:
        return ""
    return tx("pixel_sentence", L, y0=runs[0][0], y1=runs[-1][1], n=len(runs),
              cls=runs[-1][2])


def age_sentence(summary: dict[str, Any], radius: float, lang: str = "pt",
                 scope: str = "point", n: int = 0, shape: str = "circle") -> str:
    """Constraint C5: the censored share is always in the sentence."""
    L = text_lang(lang)
    if not summary:
        return ""
    kw = dict(scope=scope_phrase(scope, radius, L, n, shape),
              cpct=fmt_pct(summary.get("censored_pct"), 1, L),
              cha=fmt_ha(summary.get("censored_area_ha"), 0, L), c=fa.CENSORED_AGE)
    median = summary.get("median_dated_age")
    if median is None:
        return tx("age_sentence_all_censored", L, **kw)
    return tx("age_sentence", L, median=fmt_int(median, L), **kw)


def age_point_sentence(age_point: pd.DataFrame, lang: str = "pt") -> str:
    L = text_lang(lang)
    if age_point is None or age_point.empty or "age" not in age_point.columns:
        return ""
    last = age_point.sort_values("year").iloc[-1]
    age, year = last.get("age"), int(last["year"])
    if age is None or age != age:
        return ""
    age = int(age)
    if age >= fa.CENSORED_AGE:
        return tx("age_point_censored", L, y=year, c=fa.CENSORED_AGE)
    if age == 0:
        return tx("age_point_zero", L, y=year)
    return tx("age_point_sentence", L, y=year, age=age)


def change_sentence(row: dict[str, float], radius: float, lang: str = "pt",
                    y0: int = 2008, shape: str = "circle") -> str:
    L = text_lang(lang)
    if not row:
        return ""
    return tx("change_sentence", L, y0=y0, radius=radius_label(radius, shape, L),
              loss=fmt_ha(row.get("loss_ha", 0.0), 0, L),
              gain=fmt_ha(row.get("gain_ha", 0.0), 0, L),
              stable=fmt_ha(row.get("stable_ha", 0.0), 0, L))


def biomass_sentence(biomass: pd.DataFrame, radius: float, lang: str = "pt",
                     scope: str = "point", n: int = 0, shape: str = "circle") -> str:
    L = text_lang(lang)
    sub = _at(biomass, radius)
    if sub.empty or "agb_mean_mgha" not in sub.columns:
        return ""
    sub = sub.sort_values("year")
    b0, b1 = float(sub["agb_mean_mgha"].iloc[0]), float(sub["agb_mean_mgha"].iloc[-1])
    return tx("biomass_sentence", L, scope=scope_phrase(scope, radius, L, n, shape),
              b0=fmt_num(b0, 1, L), y0=int(sub["year"].iloc[0]), b1=fmt_num(b1, 1, L),
              y1=int(sub["year"].iloc[-1]), d=fmt_signed(b1 - b0, 1, L))


def landscape_sentence(metrics: pd.DataFrame, radius: float, lang: str = "pt",
                       scope: str = "point", n: int = 0, shape: str = "circle") -> str:
    L = text_lang(lang)
    sub = _at(metrics, radius)
    if sub.empty:
        return ""
    row = sub.iloc[0]
    return tx("landscape_sentence", L, scope=scope_phrase(scope, radius, L, n, shape),
              patches=fmt_int(row.get("patches"), L),
              lpi=fmt_pct(row.get("largest_patch_pct"), 1, L),
              ed=fmt_num(row.get("edge_density"), 1, L))


def connectivity_sentence(connectivity: pd.DataFrame, radius: float,
                          lang: str = "pt", shape: str = "circle") -> str:
    L = text_lang(lang)
    sub = _at(connectivity, radius)
    if sub.empty:
        return ""
    row = sub.iloc[0]
    median = row.get("enn_median_m")
    if median is None or median != median:
        return ""
    return tx("connectivity_sentence", L, radius=radius_label(radius, shape, L),
              n=fmt_int(row.get("n_fragments"), L), median=fmt_int(median, L))


def ibge_sentence(matrix: dict[str, Any], radius: float, lang: str = "pt",
                  scope: str = "point", n: int = 0, shape: str = "circle") -> str:
    L = text_lang(lang)
    if not matrix or not matrix.get("matrix"):
        return ""
    return tx("ibge_sentence", L, scope=scope_phrase(scope, radius, L, n, shape),
              fi=fmt_pct(matrix.get("forest_ibge"), 1, L),
              fm=fmt_pct(matrix.get("forest_mb"), 1, L),
              ni=fmt_pct(matrix.get("natural_ibge"), 1, L),
              nm=fmt_pct(matrix.get("natural_mb"), 1, L))


def gbif_sentence(row: dict[str, Any], lang: str = "pt", shape: str = "circle") -> str:
    L = text_lang(lang)
    if not row:
        return ""
    return tx("gbif_sentence", L, radius=radius_label(float(row["radius_km"]), shape, L),
              total=fmt_int(row.get("total"), L), richness=fmt_int(row.get("richness"), L))


def per_point_sentence(shares: Sequence[float], radius: float, year: int,
                       lang: str = "pt", shape: str = "circle") -> str:
    L = text_lang(lang)
    vals = [v for v in shares if v is not None and v == v]
    if not vals:
        return ""
    return tx("per_point_sentence", L, n=len(vals), radius=radius_label(radius, shape, L),
              y1=year, lo=fmt_pct(min(vals), 1, L), hi=fmt_pct(max(vals), 1, L))
