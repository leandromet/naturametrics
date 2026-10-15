"""MapBiomas Brazil land use and cover: collections, class names, colours, palette.

One table for the whole UmaTerra suite. Shared by Naturametrics, Camposcope,
Yvynation and Clima (muda-clima), and checked by hash: the canonical copy is
``/server/naturametrics/naturametrics/config/mapbiomas_legend.py``. Edit it
there, then run ``python scripts/sync_shared_files.py`` in Naturametrics. An
edit made in any other copy fails that app's ``tests/test_shared_files.py``.
Pure Python (no Reflex, no Earth Engine import), so every app can use it.

**Source.** Codes currently mapped (Collection 11) come from MapBiomas' official
legend file, ``legend_code_mapbiomas_brazil_collection_11.csv`` (brasil.mapbiomas.org,
"Códigos de Legenda", published 2026-08). Two typos in its English names are
fixed here ("Outrcrop", "Coffe"). Codes that only older collections use keep the
names and colours the suite had before.

**What Collection 11 changed** (measured over Brazil, 2024–2025 bands):

* 77 Formação Herbácea Arbustiva is the old 13 (the asset says ``13->77``);
* 7 is now *Savana Alagada (beta)*. In older tables 7 meant "Flooded Forest",
  which no recent collection maps;
* new: 84 Marismas (beta), 91 Parque eólico (beta). 75 Usina Fotovoltaica was
  already in 10.1, but the suite's palette stopped at 62 and drew it in the
  wrong colour;
* recoloured: 29 Afloramento Rochoso ``#ad5100`` and 50 Restinga Herbácea
  ``#ffaa5f`` (swapped from before), 33 Rio, Lago e Oceano ``#2532e4``;
* no more 0 (no data) inside Brazil.

The official palette is prescribed and is not colour-blind safe. Always show a
swatch together with its label.
"""

from __future__ import annotations

_ROOT = "projects/mapbiomas-public/assets/brazil/lulc"

#: Coverage image per collection; one band per year, ``classification_<year>``.
COLLECTIONS: dict[str, str] = {
    "v11": f"{_ROOT}/collection11/mapbiomas_brazil_collection11_coverage_v3",
    "v10_1": f"{_ROOT}/collection10_1/mapbiomas_brazil_collection10_1_coverage_v1",
    "v9": f"{_ROOT}/collection9/mapbiomas_collection90_integration_v1",
    "v8": f"{_ROOT}/collection8/mapbiomas_collection80_integration_v1",
}

#: First and last year with a band, per collection.
YEARS: dict[str, tuple[int, int]] = {
    "v11": (1985, 2025),
    "v10_1": (1985, 2024),
    "v9": (1985, 2023),
    "v8": (1985, 2022),
}

#: Human names for citations, reports and provenance lines.
NAMES: dict[str, str] = {
    "v11": "MapBiomas Collection 11",
    "v10_1": "MapBiomas Collection 10.1",
    "v9": "MapBiomas Collection 9",
    "v8": "MapBiomas Collection 8",
}

DEFAULT_COLLECTION = "v11"

#: Deforestation and secondary vegetation (DSV): classes 1–7, unchanged from
#: 10.1 ``v3`` to 11 ``v5``. Its bands start in 1987.
DSV_COLLECTIONS: dict[str, str] = {
    "v11": f"{_ROOT}/collection11/mapbiomas_brazil_collection11_deforestation_secondary_vegetation_v5",
    "v10_1": f"{_ROOT}/collection10_1/mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3",
}
DSV_YEARS: dict[str, tuple[int, int]] = {"v11": (1987, 2025), "v10_1": (1987, 2024)}


def band_for_year(year: int) -> str:
    return f"classification_{year}"


def years(collection: str = DEFAULT_COLLECTION) -> list[int]:
    start, end = YEARS[collection]
    return list(range(start, end + 1))


def latest_year(collection: str = DEFAULT_COLLECTION) -> int:
    return YEARS[collection][1]


# --------------------------------------------------------------------------- #
# Class names
# --------------------------------------------------------------------------- #

LABELS_PT: dict[int, str] = {
    # Collection 11 — official legend
    3: "Formação Florestal",
    4: "Formação Savânica",
    5: "Mangue",
    6: "Floresta Alagável",
    7: "Savana Alagada (beta)",
    9: "Silvicultura",
    11: "Campo Alagado e Área Pantanosa",
    12: "Formação Campestre",
    15: "Pastagem",
    20: "Cana",
    21: "Mosaico de Usos",
    23: "Praia, Duna e Areal",
    24: "Área Urbanizada",
    25: "Outras Áreas não Vegetadas",
    29: "Afloramento Rochoso",
    30: "Mineração",
    31: "Aquicultura",
    32: "Apicum",
    33: "Rio, Lago e Oceano",
    35: "Dendê",
    39: "Soja",
    40: "Arroz",
    41: "Outras Lavouras Temporárias",
    46: "Café",
    47: "Citrus",
    48: "Outras Lavouras Perenes",
    49: "Restinga Arbórea",
    50: "Restinga Herbácea ou Arbustiva",
    62: "Algodão (beta)",
    75: "Usina Fotovoltaica",
    77: "Formação Herbácea Arbustiva",
    84: "Marismas (beta)",
    91: "Parque Eólico (beta)",
    # Higher legend levels
    1: "Floresta",
    10: "Vegetação Herbácea e Arbustiva",
    14: "Agropecuária",
    18: "Agricultura",
    19: "Lavoura Temporária",
    22: "Área não Vegetada",
    26: "Corpo d'Água",
    36: "Lavoura Perene",
    # Older collections only
    0: "Sem dados",
    2: "Floresta Natural",
    8: "Restinga Arbustiva",
    13: "Outras Formações não Florestais",
    16: "Agricultura",
    17: "Lavoura Perene",
    27: "Não observado",
    28: "Afloramento Rochoso",
    34: "Reservatório",
    37: "Lavoura Semi-Perene",
    38: "Lavoura Anual",
    42: "Outra Lavoura Anual",
    43: "Outra Lavoura Semi-Perene",
    44: "Outra Lavoura Perene",
    45: "Café",
    51: "Salina",
    52: "Apicuns e Salinas",
    146: "Outro Uso da Terra",
    435: "Outra Transição",
    466: "Outra Classificação",
}

LABELS_EN: dict[int, str] = {
    3: "Forest Formation",
    4: "Savanna Formation",
    5: "Mangrove",
    6: "Floodable Forest",
    7: "Flooded Savanna (beta)",
    9: "Forest Plantation",
    11: "Wetland",
    12: "Grassland Formation",
    15: "Pasture",
    20: "Sugar Cane",
    21: "Mosaic of Uses",
    23: "Beach, Dune and Sand Spot",
    24: "Urban Area",
    25: "Other non Vegetated Areas",
    29: "Rocky Outcrop",
    30: "Mining",
    31: "Aquaculture",
    32: "Hypersaline Tidal Flat",
    33: "River, Lake and Ocean",
    35: "Palm Oil",
    39: "Soybean",
    40: "Rice",
    41: "Other Temporary Crops",
    46: "Coffee",
    47: "Citrus",
    48: "Other Perennial Crops",
    49: "Wooded Sandbank Vegetation",
    50: "Herbaceous Sandbank Vegetation",
    62: "Cotton (beta)",
    75: "Photovoltaic Power Plant",
    77: "Herbaceous and Shrub Formation",
    84: "Salt Marsh (beta)",
    91: "Wind Farm (beta)",
    1: "Forest",
    10: "Herbaceous and Shrub Vegetation",
    14: "Farming",
    18: "Agriculture",
    19: "Temporary Crop",
    22: "Non vegetated area",
    26: "Water",
    36: "Perennial Crop",
    0: "No data",
    2: "Natural Forest",
    8: "Wooded Restinga",
    13: "Other Natural Formation",
    16: "Agriculture",
    17: "Perennial Crop",
    27: "Not Observed",
    28: "Rocky Outcrop",
    34: "Reservoir",
    37: "Semi-Perennial Crop",
    38: "Annual Crop",
    42: "Other Annual Crop",
    43: "Other Semi-Perennial Crop",
    44: "Other Perennial Crop",
    45: "Coffee",
    51: "Salt Flat",
    52: "Apicuns and Salines",
    146: "Other Land Use",
    435: "Other Transition",
    466: "Other Classification",
}

LABELS: dict[str, dict[int, str]] = {"pt": LABELS_PT, "en": LABELS_EN}


def label(code: int, lang: str = "pt") -> str:
    """Class name in Portuguese, or English for any other language."""
    table = LABELS_PT if lang == "pt" else LABELS_EN
    return table.get(code, f"Classe {code}" if lang == "pt" else f"Class {code}")


# --------------------------------------------------------------------------- #
# Colours
# --------------------------------------------------------------------------- #

COLORS: dict[int, str] = {
    # Collection 11 — official legend
    3: "#1f8d49", 4: "#7dc975", 5: "#04381d", 6: "#007785", 7: "#228c70",
    9: "#7a5900", 11: "#519799", 12: "#d6bc74", 15: "#edde8e", 20: "#db7093",
    21: "#ffefc3", 23: "#ffa07a", 24: "#d4271e", 25: "#db4d4f", 29: "#ad5100",
    30: "#9c0027", 31: "#091077", 32: "#fc8114", 33: "#2532e4", 35: "#9065d0",
    39: "#f5b3c8", 40: "#c71585", 41: "#f54ca9", 46: "#d68fe2", 47: "#9932cc",
    48: "#e6ccff", 49: "#02d659", 50: "#ffaa5f", 62: "#ff69b4", 75: "#757272",
    77: "#86b074", 84: "#81dbbf", 91: "#403d3e",
    # Higher legend levels
    1: "#1f8d49", 10: "#d6bc74", 14: "#ffefc3", 18: "#e974ed", 19: "#c27ba0",
    22: "#d4271e", 26: "#2532e4", 36: "#d082de",
    # Older collections only
    0: "#ffffff", 2: "#1f8d49", 8: "#33a02c", 13: "#ffffff", 16: "#e974ed",
    17: "#d082de", 27: "#ffffff", 28: "#ffaa5f", 34: "#259fe4", 37: "#d082de",
    38: "#c27ba0", 42: "#f54ca9", 43: "#d082de", 44: "#d082de", 45: "#d68fe2",
    51: "#fc8114", 52: "#fc8114", 146: "#ffefc3", 435: "#cccccc", 466: "#999999",
}

#: Fill for codes with no assigned swatch, so a gap shows as a gap.
GAP_COLOR = "808080"

#: Highest code any collection maps. The palette must reach it: Earth Engine
#: clamps values above ``max`` to the last colour.
MAX_CODE = 91

#: Dense 0..MAX_CODE palette (hex without ``#``) for ``getMapId``.
PALETTE: list[str] = [COLORS[i].lstrip("#") if i in COLORS else GAP_COLOR
                      for i in range(MAX_CODE + 1)]

VIS: dict = {"min": 0, "max": MAX_CODE, "palette": PALETTE}


def color(code: int) -> str:
    """Hex colour (with ``#``) for a class code."""
    return COLORS.get(code, f"#{GAP_COLOR}")
