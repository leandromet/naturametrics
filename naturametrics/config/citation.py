"""Who made this, how to cite it, and what must be credited.

Lives in ``config`` rather than beside the dialog that displays it because
constraint **C4** (doc/01-premises.md) applies to *every* way the facts leave the
app — the "Como citar" panel and the metadata sheet of every export both have to
say the same thing, and two copies drift.

``DATA_SOURCES``/``DATA_SOURCES_EN`` below list every dataset **either** page
draws on, Brazil and Canada alike, and both pages' "How to cite" dialogs read
this same list (``naturametrics/components/help.py::como_citar_dialog`` and
``naturametrics/canada/components/help.py::how_to_cite_dialog``) rather than
each maintaining its own subset — a reader of either page should be able to see
everything Naturametrics as a whole is built on, not just the half their
current page happens to touch. The Canada export workbook's own metadata sheet
(``canada/services/exports.py``) keeps a separate, page-scoped list for that
purpose; only the two "How to cite" dialogs are unified.
"""

from __future__ import annotations

APP_URL = "https://naturametrics-652582010777.us-west1.run.app"
APP_YEAR = "2026"

AUTHORS = [
    ("Leandro Meneguelli Biondo", "University of British Columbia Okanagan (UBC Okanagan), Canadá"),
    ("Gustavo Heringer", "Instituto Nacional da Mata Atlântica (INMA/MCTI), Brasil"),
    ("Alex Coelho", "Universidade Federal de Viçosa (UFV), Brasil"),
    ("João Augusto Alves Meira-Neto", "Universidade Federal de Viçosa (UFV), Brasil"),
]

#: Same list, institution country name in English — everything else about an
#: author's affiliation (the institution itself, its acronym) is already in
#: English or is a proper noun, so only "Canadá"/"Brasil" actually differ.
AUTHORS_EN = [
    (name, inst.replace("Canadá", "Canada").replace("Brasil", "Brazil"))
    for name, inst in AUTHORS
]

CITATION_TEXT = (
    "Biondo, L. M.; Heringer, G.; Coelho, A.; Meira-Neto, J. A. A. "
    f"({APP_YEAR}). Naturametrics: história de uso da terra e análise da paisagem. "
    "University of British Columbia Okanagan; Instituto Nacional da Mata "
    "Atlântica (INMA/MCTI); Universidade Federal de Viçosa. "
    f"Disponível em: {APP_URL}"
)

BIBTEX = f"""@software{{naturametrics_{APP_YEAR},
  title   = {{Naturametrics: história de uso da terra e análise da paisagem}},
  author  = {{Biondo, Leandro Meneguelli and Heringer, Gustavo and Coelho, Alex
              and Meira-Neto, João Augusto Alves}},
  year    = {{{APP_YEAR}}},
  organization = {{University of British Columbia Okanagan; Instituto Nacional
                   da Mata Atlântica (INMA/MCTI); Universidade Federal de Viçosa}},
  url     = {{{APP_URL}}}
}}"""

#: Constraint C4 — every layer the app can draw is credited here.
DATA_SOURCES = [
    ("MapBiomas — Coleção 11",
     "Projeto MapBiomas — Mapeamento Anual de Cobertura e Uso da Terra no Brasil. "
     "Licença CC-BY-SA.",
     "https://mapbiomas.org"),
    ("MapBiomas — Desmatamento e Vegetação Secundária",
     "Base do cálculo de regeneração e do ano de referência do Código Florestal.",
     "https://mapbiomas.org"),
    ("ESA CCI Biomass (Biomass_cci) v6.0",
     "Santoro, M.; Cartus, O. (2025). ESA Biomass Climate Change Initiative "
     "(Biomass_cci): Global datasets of forest above-ground biomass for the "
     "years 2007, 2010, 2015–2022, v6.0. NERC EDS Centre for Environmental "
     "Data Analysis. doi:10.5285/95913ffb6467447ca72c4e9d8cf30501. "
     "Base da aba «Biomassa».",
     "https://doi.org/10.5285/95913ffb6467447ca72c4e9d8cf30501"),
    ("Hansen Global Forest Change",
     "Hansen, M. C. et al. (2013). High-Resolution Global Maps of 21st-Century "
     "Forest Cover Change. Science 342, 850–853. Licença CC-BY 4.0. Usado nas "
     "páginas Brasil e Canadá.",
     "https://glad.earthengine.app/view/global-forest-change"),
    ("Inventário Florestal Nacional (IFN)",
     "Serviço Florestal Brasileiro — dados abertos, licença CC-BY.",
     "https://dados.florestal.gov.br"),
    ("AAFC — Inventário Anual de Culturas",
     "Agriculture and Agri-Food Canada. Licença Open Government — Canadá. "
     "Usado na página Canadá.",
     "https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI"),
    ("USGS — Annual NLCD (EUA)",
     "U.S. Geological Survey. Annual National Land Cover Database, Collection 1 "
     "v2, 1985–2025 (48 estados contíguos). Domínio público. Base da página dos EUA.",
     "https://www.usgs.gov/centers/eros/science/annual-national-land-cover-database"),
    ("NTEMS — Idade da floresta (Canadá, 2019)",
     "Natural Resources Canada / National Forest Information System; "
     "Hermosilla et al. Usado na página Canadá.",
     "https://developers.google.com/earth-engine/datasets/catalog/"
     "CANADA_NFIS_NTEMS_CA_FOREST_AGE"),
    ("Composições anuais Landsat",
     "USGS/NASA Landsat Collection 2 Tier 1 Level-2, composições anuais. "
     "Usado na página Canadá.",
     "https://developers.google.com/earth-engine/datasets/catalog/"
     "LANDSAT_COMPOSITES_C02_T1_L2_ANNUAL"),
    ("IBAMA — Áreas embargadas",
     "Instituto Brasileiro do Meio Ambiente e dos Recursos Naturais Renováveis "
     "— áreas embargadas por infração ambiental, serviço de mapas oficial "
     "(PAMGIA), consultado ao vivo por vista do mapa. Dados abertos.",
     "https://pamgia.ibama.gov.br"),
    ("IBAMA — Autos de infração",
     "Instituto Brasileiro do Meio Ambiente e dos Recursos Naturais Renováveis "
     "— autos de infração ambiental, serviço de mapas oficial (PAMGIA), "
     "consultado ao vivo por vista do mapa. Dados abertos. Um auto de infração "
     "é a autuação em si; o embargo é a restrição sobre a área, e nem toda "
     "autuação gera embargo.",
     "https://pamgia.ibama.gov.br"),
    ("IBGE — Biomas, vegetação e malhas municipais",
     "Instituto Brasileiro de Geografia e Estatística — Biomas do Brasil; "
     "Vegetação 2022; Malhas territoriais municipais 2025. Usados como camadas "
     "de referência e para enquadrar o mapa.",
     "https://www.ibge.gov.br"),
    ("Funai — Terras Indígenas",
     "Fundação Nacional dos Povos Indígenas — poligonais e portarias das "
     "terras indígenas. Camada de referência e busca; limites simplificados "
     "(~200 m), não determinam se um ponto está dentro de uma terra "
     "indígena.",
     "https://www.gov.br/funai"),
    ("ICMBio/MMA — Cadastro Nacional de Unidades de Conservação (CNUC)",
     "Ministério do Meio Ambiente e ICMBio — CNUC, unidades de conservação "
     "federais, estaduais e municipais. Camada de referência e busca; limites "
     "simplificados (~200 m), não determinam se um ponto está dentro de uma "
     "unidade de conservação.",
     "https://www.gov.br/icmbio"),
    ("GBIF — Registros de ocorrência de espécies",
     "GBIF.org — Global Biodiversity Information Facility. Registros "
     "consultados ao vivo pela API de ocorrências, restritos ao Brasil. Ao "
     "publicar resultados, cite a consulta e a data de acesso no formato "
     "recomendado pelo GBIF («GBIF.org (dd mmm aaaa) GBIF Occurrence Search») "
     "e credite os conjuntos de dados de origem, que têm licenças próprias "
     "(CC0, CC-BY e CC-BY-NC). ATENÇÃO: esta consulta NÃO exclui dados "
     "CC-BY-NC, que vedam uso comercial. O nó brasileiro do GBIF é o SiBBr.",
     "https://www.gbif.org"),
    ("Google Earth Engine",
     "Gorelick, N. et al. (2017). Google Earth Engine: Planetary-scale geospatial "
     "analysis for everyone. Remote Sensing of Environment 202, 18–27.",
     "https://earthengine.google.com"),
    ("Mapas base",
     "Esri World Imagery; OpenStreetMap contributors; Google.",
     "https://www.openstreetmap.org/copyright"),
]

#: Same sources, name/description in English — used only by the "How to cite"
#: dialogs in English mode. The exported spreadsheets' own metadata sheets
#: always cite from their page-scoped Portuguese/English lists (Brazil's from
#: the Portuguese list above regardless of UI language, matching CITATION_TEXT;
#: Canada's from canada/services/exports.py::DATA_SOURCES) — only the two "How
#: to cite" dialogs draw from this shared, bilingual, both-countries list.
DATA_SOURCES_EN = [
    ("MapBiomas — Collection 11",
     "MapBiomas Project — Annual Land Use and Land Cover Mapping in Brazil. "
     "CC-BY-SA license.",
     "https://mapbiomas.org"),
    ("MapBiomas — Deforestation and Secondary Vegetation",
     "Basis for the regrowth calculation and the Forest Code baseline year.",
     "https://mapbiomas.org"),
    ("ESA CCI Biomass (Biomass_cci) v6.0",
     "Santoro, M.; Cartus, O. (2025). ESA Biomass Climate Change Initiative "
     "(Biomass_cci): Global datasets of forest above-ground biomass for the "
     "years 2007, 2010, 2015–2022, v6.0. NERC EDS Centre for Environmental "
     "Data Analysis. doi:10.5285/95913ffb6467447ca72c4e9d8cf30501. "
     "Basis of the «Biomass» tab.",
     "https://doi.org/10.5285/95913ffb6467447ca72c4e9d8cf30501"),
    ("Hansen Global Forest Change",
     "Hansen, M. C. et al. (2013). High-Resolution Global Maps of 21st-Century "
     "Forest Cover Change. Science 342, 850–853. CC-BY 4.0 license. Used on "
     "the Brazil and Canada pages.",
     "https://glad.earthengine.app/view/global-forest-change"),
    ("National Forest Inventory (IFN)",
     "Brazilian Forest Service — open data, CC-BY license.",
     "https://dados.florestal.gov.br"),
    ("AAFC — Annual Crop Inventory",
     "Agriculture and Agri-Food Canada. Open Government Licence — Canada. "
     "Used on the Canada page.",
     "https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI"),
    ("USGS — Annual NLCD (US)",
     "U.S. Geological Survey. Annual National Land Cover Database, Collection 1 "
     "v2, 1985–2025 (conterminous US). Public domain. Basis of the USA page.",
     "https://www.usgs.gov/centers/eros/science/annual-national-land-cover-database"),
    ("NTEMS — Canada forest age (2019)",
     "Natural Resources Canada / National Forest Information System; "
     "Hermosilla et al. Used on the Canada page.",
     "https://developers.google.com/earth-engine/datasets/catalog/"
     "CANADA_NFIS_NTEMS_CA_FOREST_AGE"),
    ("Landsat annual composites",
     "USGS/NASA Landsat Collection 2 Tier 1 Level-2 annual composites. Used "
     "on the Canada page.",
     "https://developers.google.com/earth-engine/datasets/catalog/"
     "LANDSAT_COMPOSITES_C02_T1_L2_ANNUAL"),
    ("IBAMA — Embargoed areas",
     "Brazilian Institute of Environment and Renewable Natural Resources — "
     "areas embargoed for environmental infraction, from the official map "
     "service (PAMGIA), queried live per map view. Open data.",
     "https://pamgia.ibama.gov.br"),
    ("IBAMA — Infraction notices",
     "Brazilian Institute of Environment and Renewable Natural Resources — "
     "environmental infraction notices, from the official map service "
     "(PAMGIA), queried live per map view. Open data. An infraction notice is "
     "the citation itself; an embargo is the restriction on the land, and not "
     "every citation carries one.",
     "https://pamgia.ibama.gov.br"),
    ("IBGE — Biomes, vegetation and municipal boundaries",
     "Brazilian Institute of Geography and Statistics — Biomes of Brazil; "
     "Vegetation 2022; Municipal boundary meshes 2025. Used as reference "
     "layers and to frame the map.",
     "https://www.ibge.gov.br"),
    ("Funai — Indigenous lands",
     "Fundação Nacional dos Povos Indígenas — indigenous land polygons and "
     "the ordinances behind them. Reference and search layer; boundaries "
     "simplified (~200 m) and do not determine whether a point falls inside "
     "an indigenous land.",
     "https://www.gov.br/funai"),
    ("ICMBio/MMA — National Registry of Conservation Units (CNUC)",
     "Ministry of the Environment and ICMBio — CNUC, federal, state and "
     "municipal conservation units. Reference and search layer; boundaries "
     "simplified (~200 m) and do not determine whether a point falls inside "
     "a conservation unit.",
     "https://www.gov.br/icmbio"),
    ("GBIF — Species occurrence records",
     "GBIF.org — Global Biodiversity Information Facility. Records queried "
     "live through the occurrence API, restricted to Brazil. When publishing "
     "results, cite the query and access date in GBIF's recommended form "
     "(\u201cGBIF.org (dd mmm yyyy) GBIF Occurrence Search\u201d) and credit the "
     "constituent datasets, which carry their own licences (CC0, CC-BY and "
     "CC-BY-NC). NOTE: this query does NOT exclude CC-BY-NC data, which "
     "prohibits commercial use. GBIF's Brazilian node is SiBBr.",
     "https://www.gbif.org"),
    ("Google Earth Engine",
     "Gorelick, N. et al. (2017). Google Earth Engine: Planetary-scale geospatial "
     "analysis for everyone. Remote Sensing of Environment 202, 18–27.",
     "https://earthengine.google.com"),
    ("Base maps",
     "Esri World Imagery; OpenStreetMap contributors; Google.",
     "https://www.openstreetmap.org/copyright"),
]


#: What the World page (/mundo) uses: its own land-cover and climate sources first, then the shared ones it
#: also draws (forest change, biomass, imagery, GBIF, Earth Engine, base maps). Same shape as the lists above.
_WORLD_OWN_PT = [
    ("GLC-FCS30D — cobertura do solo global, 30 m",
     "Zhang, X. et al. (2024). GLC_FCS30D: the first global 30-m land-cover dynamics monitoring product with a "
     "fine classification system for the period from 1985 to 2022. Earth System Science Data 16, 1353–1381. "
     "doi:10.5194/essd-16-1353-2024. Dados: Zenodo, doi:10.5281/zenodo.8239305. Licença CC BY 4.0. "
     "Base do histórico de cobertura do solo (2000–2022).",
     "https://doi.org/10.5281/zenodo.8239305"),
    ("NASA NEX-GDDP-CMIP6",
     "Thrasher, B. et al. (2022). NASA Global Daily Downscaled Projections, CMIP6. Scientific Data 9, 262. "
     "doi:10.1038/s41597-022-01393-4. Nove modelos, 0,25°, lidos em células de 0,5° na aba «Clima». "
     "Licença CC0 (desde set/2022); os termos de uso do CMIP6 de origem continuam valendo.",
     "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6"),
    ("Köppen-Geiger 1 km (Beck et al. 2023)",
     "Beck, H. E. et al. (2023). Scientific Data 10, 724. doi:10.1038/s41597-023-02549-6. "
     "Classes climáticas 1991–2020 e 2041–2070. Licença CC BY 4.0.",
     "https://doi.org/10.6084/m9.figshare.21789074"),
]
_WORLD_OWN_EN = [
    ("GLC-FCS30D — global land cover, 30 m",
     "Zhang, X. et al. (2024). GLC_FCS30D: the first global 30-m land-cover dynamics monitoring product with a "
     "fine classification system for the period from 1985 to 2022. Earth System Science Data 16, 1353–1381. "
     "doi:10.5194/essd-16-1353-2024. Data: Zenodo, doi:10.5281/zenodo.8239305. Licence CC BY 4.0. "
     "Basis of the land-cover history (2000–2022).",
     _WORLD_OWN_PT[0][2]),
    ("NASA NEX-GDDP-CMIP6",
     "Thrasher, B. et al. (2022). NASA Global Daily Downscaled Projections, CMIP6. Scientific Data 9, 262. "
     "doi:10.1038/s41597-022-01393-4. Nine models, 0.25°, read in 0.5° cells in the «Climate» tab. "
     "Licence CC0 (since Sep 2022); the upstream CMIP6 terms of use still apply.",
     _WORLD_OWN_PT[1][2]),
    ("Köppen-Geiger 1 km (Beck et al. 2023)",
     "Beck, H. E. et al. (2023). Scientific Data 10, 724. doi:10.1038/s41597-023-02549-6. "
     "Climate classes 1991–2020 and 2041–2070. Licence CC BY 4.0.",
     _WORLD_OWN_PT[2][2]),
]
_WORLD_SHARED = ("Hansen Global Forest Change", "ESA CCI Biomass (Biomass_cci) v6.0", "Composições anuais Landsat",
                 "GBIF — Registros de ocorrência de espécies", "Google Earth Engine", "Mapas base")
_pairs = [(pt, en) for pt, en in zip(DATA_SOURCES, DATA_SOURCES_EN) if pt[0] in _WORLD_SHARED]
WORLD_SOURCES = _WORLD_OWN_PT + [pt for pt, _ in _pairs]
WORLD_SOURCES_EN = _WORLD_OWN_EN + [en for _, en in _pairs]
