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
    ("MapBiomas — Coleção 10.1",
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
    ("MapBiomas — Collection 10.1",
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
    ("Google Earth Engine",
     "Gorelick, N. et al. (2017). Google Earth Engine: Planetary-scale geospatial "
     "analysis for everyone. Remote Sensing of Environment 202, 18–27.",
     "https://earthengine.google.com"),
    ("Base maps",
     "Esri World Imagery; OpenStreetMap contributors; Google.",
     "https://www.openstreetmap.org/copyright"),
]
