"""Who made this, how to cite it, and what must be credited.

Lives in ``config`` rather than beside the dialog that displays it because
constraint **C4** (doc/01-premises.md) applies to *every* way the facts leave the
app — the "Como citar" panel and the metadata sheet of every export both have to
say the same thing, and two copies drift.
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
    ("Hansen Global Forest Change",
     "Hansen, M. C. et al. (2013). High-Resolution Global Maps of 21st-Century "
     "Forest Cover Change. Science 342, 850–853. Licença CC-BY 4.0.",
     "https://glad.earthengine.app/view/global-forest-change"),
    ("Inventário Florestal Nacional (IFN)",
     "Serviço Florestal Brasileiro — dados abertos, licença CC-BY.",
     "https://dados.florestal.gov.br"),
    ("Google Earth Engine",
     "Gorelick, N. et al. (2017). Google Earth Engine: Planetary-scale geospatial "
     "analysis for everyone. Remote Sensing of Environment 202, 18–27.",
     "https://earthengine.google.com"),
    ("Mapas base",
     "Esri World Imagery; OpenStreetMap contributors; Google.",
     "https://www.openstreetmap.org/copyright"),
]
