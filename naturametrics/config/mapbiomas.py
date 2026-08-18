"""MapBiomas class labels, colours and palette.

Ported from Yvynation's ``config/config.py`` and extended with Portuguese labels
(the domain is Brazilian; PT is the source language — see doc/07-ui-ux.md §7).

Collection 10.1 is the default; older collections are kept for comparison work.
"""

from __future__ import annotations

from typing import Dict, List

# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #

MAPBIOMAS_COLLECTIONS: Dict[str, str] = {
    "v10_1": (
        "projects/mapbiomas-public/assets/brazil/lulc/collection10_1/"
        "mapbiomas_brazil_collection10_1_coverage_v1"
    ),
    "v9": (
        "projects/mapbiomas-public/assets/brazil/lulc/collection9/"
        "mapbiomas_collection90_integration_v1"
    ),
    "v8": (
        "projects/mapbiomas-public/assets/brazil/lulc/collection8/"
        "mapbiomas_collection80_integration_v1"
    ),
}

MAPBIOMAS_DEFAULT_COLLECTION = "v10_1"

#: Collection 10.1 ships one band per year: ``classification_1985`` … ``_2024``.
MAPBIOMAS_YEAR_START = 1985
MAPBIOMAS_YEAR_END = 2024
MAPBIOMAS_YEARS: List[int] = list(range(MAPBIOMAS_YEAR_START, MAPBIOMAS_YEAR_END + 1))


def band_for_year(year: int) -> str:
    """Band name for a MapBiomas year."""
    return f"classification_{year}"


def all_bands() -> List[str]:
    """Every classification band — the basis of the batched history query.

    See doc/06-ee-layers.md §4: selecting all of these and reducing once is what
    turns 40 sequential round-trips into one.
    """
    return [band_for_year(y) for y in MAPBIOMAS_YEARS]


# --------------------------------------------------------------------------- #
# Class labels
# --------------------------------------------------------------------------- #
# Codes follow Yvynation's table so the two apps agree. Some codes are legacy or
# duplicated upstream (1/2/3 are all forest-ish; 29 appears twice in the source
# table) — that is a property of the published legend, not a transcription error.
# See D6 in doc/09-open-decisions.md before treating this as normative.

MAPBIOMAS_LABELS_PT: Dict[int, str] = {
    0: "Sem dados",
    1: "Floresta",
    2: "Floresta Natural",
    3: "Formação Florestal",
    4: "Formação Savânica",
    5: "Mangue",
    6: "Floresta Alagável",
    7: "Floresta Inundada",
    8: "Restinga Arbustiva",
    9: "Silvicultura",
    10: "Formação Natural não Florestal",
    11: "Campo Alagado e Área Pantanosa",
    12: "Formação Campestre",
    13: "Outras Formações não Florestais",
    14: "Agropecuária",
    15: "Pastagem",
    16: "Agricultura",
    17: "Lavoura Perene",
    18: "Agricultura",
    19: "Lavoura Temporária",
    20: "Cana",
    21: "Mosaico de Usos",
    22: "Área não Vegetada",
    23: "Praia, Duna e Areal",
    24: "Área Urbanizada",
    25: "Outras Áreas não Vegetadas",
    26: "Corpo d'Água",
    27: "Não observado",
    28: "Afloramento Rochoso",
    29: "Afloramento Rochoso",
    30: "Mineração",
    31: "Aquicultura",
    32: "Apicum",
    33: "Rio, Lago e Oceano",
    34: "Reservatório",
    35: "Dendê",
    36: "Lavoura Perene",
    37: "Lavoura Semi-Perene",
    38: "Lavoura Anual",
    39: "Soja",
    40: "Arroz",
    41: "Outras Lavouras Temporárias",
    42: "Outra Lavoura Anual",
    43: "Outra Lavoura Semi-Perene",
    44: "Outra Lavoura Perene",
    45: "Café",
    46: "Café",
    47: "Citrus",
    48: "Outras Lavouras Perenes",
    49: "Restinga Arbórea",
    50: "Restinga Herbácea",
    51: "Salina",
    52: "Apicuns e Salinas",
    62: "Algodão",
    146: "Outro Uso da Terra",
    435: "Outra Transição",
    466: "Outra Classificação",
}

MAPBIOMAS_LABELS_EN: Dict[int, str] = {
    0: "No data",
    1: "Forest",
    2: "Natural Forest",
    3: "Forest Formation",
    4: "Savanna Formation",
    5: "Mangrove",
    6: "Floodable Forest",
    7: "Flooded Forest",
    8: "Wooded Restinga",
    9: "Forest Plantation",
    10: "Herbaceous",
    11: "Wetland",
    12: "Grassland",
    13: "Other Natural Formation",
    14: "Farming",
    15: "Pasture",
    16: "Agriculture",
    17: "Perennial Crop",
    18: "Agriculture",
    19: "Temporary Crop",
    20: "Sugar Cane",
    21: "Mosaic of Uses",
    22: "Non vegetated",
    23: "Beach and Sand",
    24: "Urban Area",
    25: "Other non Vegetated Areas",
    26: "Water",
    27: "Not Observed",
    28: "Rocky Outcrop",
    29: "Rocky Outcrop",
    30: "Mining",
    31: "Aquaculture",
    32: "Hypersaline Tidal Flat",
    33: "River Lake and Ocean",
    34: "Reservoir",
    35: "Palm Oil",
    36: "Perennial Crop",
    37: "Semi-Perennial Crop",
    38: "Annual Crop",
    39: "Soybean",
    40: "Rice",
    41: "Other Temporary Crops",
    42: "Other Annual Crop",
    43: "Other Semi-Perennial Crop",
    44: "Other Perennial Crop",
    45: "Coffee",
    46: "Coffee",
    47: "Citrus",
    48: "Other Perennial Crops",
    49: "Wooded Sandbank Vegetation",
    50: "Herbaceous Sandbank Vegetation",
    51: "Salt Flat",
    52: "Apicuns and Salines",
    62: "Cotton",
    146: "Other Land Use",
    435: "Other Transition",
    466: "Other Classification",
}

MAPBIOMAS_LABELS: Dict[str, Dict[int, str]] = {
    "pt": MAPBIOMAS_LABELS_PT,
    "en": MAPBIOMAS_LABELS_EN,
}


def label(class_id: int, lang: str = "pt") -> str:
    """Human label for a MapBiomas class code, falling back to the code itself."""
    table = MAPBIOMAS_LABELS.get(lang, MAPBIOMAS_LABELS_PT)
    return table.get(class_id, f"Classe {class_id}" if lang == "pt" else f"Class {class_id}")


# --------------------------------------------------------------------------- #
# Colours
# --------------------------------------------------------------------------- #
# The official MapBiomas palette. Prescribed, and not colour-blind safe — the
# legend always pairs swatch with label (doc/07-ui-ux.md §9).

MAPBIOMAS_COLOR_MAP: Dict[int, str] = {
    0: "#ffffff", 1: "#1f8d49", 2: "#1f8d49", 3: "#1f8d49", 4: "#7dc975",
    5: "#04381d", 6: "#007785", 7: "#005544", 8: "#33a02c", 9: "#7a5900",
    10: "#d6bc74", 11: "#519799", 12: "#d6bc74", 13: "#ffffff", 14: "#ffefc3",
    15: "#edde8e", 16: "#e974ed", 17: "#d082de", 18: "#e974ed", 19: "#c27ba0",
    20: "#db7093", 21: "#ffefc3", 22: "#d4271e", 23: "#ffa07a", 24: "#d4271e",
    25: "#db4d4f", 26: "#2532e4", 27: "#ffffff", 28: "#ffaa5f", 29: "#ffaa5f",
    30: "#9c0027", 31: "#091077", 32: "#fc8114", 33: "#259fe4", 34: "#259fe4",
    35: "#9065d0", 36: "#d082de", 37: "#d082de", 38: "#c27ba0", 39: "#f5b3c8",
    40: "#c71585", 41: "#f54ca9", 42: "#f54ca9", 43: "#d082de", 44: "#d082de",
    45: "#d68fe2", 46: "#d68fe2", 47: "#9932cc", 48: "#e6ccff", 49: "#02d659",
    50: "#ad5100", 51: "#fc8114", 52: "#fc8114", 62: "#ff69b4",
    146: "#ffefc3", 435: "#cccccc", 466: "#999999",
}

#: Fill colour for codes with no assigned swatch, so gaps are visible as gaps.
MAPBIOMAS_GAP_COLOR = "808080"

#: Dense 0..62 palette for ``getMapId`` — Earth Engine needs one entry per index
#: across the whole ``min``..``max`` range, not a sparse mapping.
MAPBIOMAS_PALETTE: List[str] = [
    MAPBIOMAS_COLOR_MAP[i].lstrip("#") if i in MAPBIOMAS_COLOR_MAP else MAPBIOMAS_GAP_COLOR
    for i in range(63)
]

MAPBIOMAS_VIS = {"min": 0, "max": 62, "palette": MAPBIOMAS_PALETTE}


def color(class_id: int) -> str:
    """Hex colour (with ``#``) for a class code."""
    return MAPBIOMAS_COLOR_MAP.get(class_id, f"#{MAPBIOMAS_GAP_COLOR}")


# --------------------------------------------------------------------------- #
# Class groups  —  PROVISIONAL, see D6
# --------------------------------------------------------------------------- #
#: The vegetation-age estimator (Phase 3) depends entirely on these groups, and
#: they have NOT yet been validated against the official Collection 10.1 legend
#: document. Three sub-questions are still open (see D6 in
#: doc/09-open-decisions.md): whether Savanna Formation counts as forest, how
#: Mosaic of Uses is treated, and confirming Forest Plantation never pools into
#: natural vegetation.
#:
#: Nothing in Phase 0–2 reads these. Do not let Phase 3 code consume them while
#: LEGEND_VALIDATED is False.
LEGEND_VALIDATED = False

FOREST_FORMATIONS = frozenset({3, 5, 6, 49})          # closed-canopy natural forest
SAVANNA_FORMATIONS = frozenset({4})                   # cerrado sensu stricto — own group
NATURAL_NON_FOREST = frozenset({10, 11, 12, 13, 29, 32, 50})
PLANTED_FOREST = frozenset({9})                       # never pooled into "natural"
WATER = frozenset({26, 33, 34, 31})
NO_DATA = frozenset({0, 27})

#: Natural vegetation = forest + savanna + natural non-forest. Savanna is
#: included here but excluded from FOREST_FORMATIONS by default.
NATURAL_VEGETATION = FOREST_FORMATIONS | SAVANNA_FORMATIONS | NATURAL_NON_FOREST
