"""IBGE Vegetação do Brasil (1:250.000, 2022 vintage) — classification, official
colours, and the shared natural/anthropic/forest taxonomy used to compare this
dataset against MapBiomas for quality control.

Source shapefile: ``vege_area`` (145,458 polygons), uploaded to Earth Engine as
:data:`IBGE_VEG_ASSET`. Symbology ported from the official QGIS style
(``simbologia_vege_area/vege_legenda2.qml``).

**Why ``legenda_2``, not ``legenda_1`` or the full ``legenda``.** The source
shapefile carries several classification fields at different granularity.
``legenda_1`` (13 classes) is native-vegetation-only — a converted polygon just
shows what it used to be, which is useless for a *current* land-use QC check.
The full ``legenda`` (211 combinations) is too fine for a legend or a stable
Earth Engine remap. ``legenda_2`` (54 classes, paired with the numeric
``leg2_id`` 1-54) is IBGE's own combined legend: natural phytoecological
subtypes *and* anthropic land uses in one field, already grouped by the
official style under three headers — Vegetação Natural, Área Antrópica, Outras
Áreas — which is exactly the natural/anthropic split this module needs.

**Why forest/non-forest reads straight off the label text.** IBGE's own
physiognomy-naming convention encodes canopy closure in the class name itself:
"Savana **Florestada**" (closed-canopy forest) vs. "Savana Arborizada"
(woodland) vs. "Savana Parque" / "... Gramíneo-Lenhosa" (open/non-forest) — the
same suffix pattern repeats across Campinarana and Savana-Estépica. No separate
canopy model is needed; :data:`IBGE_VEG_TO_GROUP` below just encodes that
reading once.

**Provenance of ``leg2_id`` -> (label, colour).** The label per ``leg2_id`` was
read from the shapefile's own ``.dbf`` (ground truth for what the asset's
``leg2_id`` property actually means — verified UTF-8 via the shapefile's
``.cpg``). The colour per label was read from the ``.qml``'s ``<symbol>``
blocks, joined **by label text**, not by symbol index: the ``.qml``'s rule
order and this shapefile's ``leg2_id`` numbering diverge from id 41 onward
(the style file inserts "Contato (Ecótono)" earlier and reorders Dunas /
Afloramento Rochoso relative to this export), so symbol-index arithmetic
(``leg2_id == symbol_name + 1``) silently mismatches classes past id 48. Joining
on the label string in the ``.qml``'s own ``filter="legenda_2 = '...'"``
clauses is what the shapefile and the style actually agree on.
"""

from __future__ import annotations

from typing import Dict

# --------------------------------------------------------------------------- #
# Asset
# --------------------------------------------------------------------------- #

IBGE_VEG_ASSET = "projects/ee-leandromet/assets/vege_area"
IBGE_VEG_CLASS_FIELD = "leg2_id"
IBGE_VEG_COUNT = 145_458
IBGE_VEG_ATTRIBUTION = "IBGE — Mapa de Vegetação do Brasil, escala 1:250.000 (2022)"

# --------------------------------------------------------------------------- #
# Class labels and official colours, leg2_id 1-54
# --------------------------------------------------------------------------- #

IBGE_VEG_LABELS_PT: Dict[int, str] = {
    1: "Floresta Ombrófila Densa Aluvial",
    2: "Floresta Ombrófila Densa das Terras Baixas",
    3: "Floresta Ombrófila Densa Submontana",
    4: "Floresta Ombrófila Densa Montana",
    5: "Floresta Ombrófila Densa Alto-Montana",
    6: "Floresta Ombrófila Aberta Aluvial",
    7: "Floresta Ombrófila Aberta das Terras Baixas",
    8: "Floresta Ombrófila Aberta Submontana",
    9: "Floresta Ombrófila Mista Montana",
    10: "Floresta Ombrófila Mista Alto-Montana",
    11: "Floresta Estacional Sempre Verde Aluvial",
    12: "Floresta Estacional Sempre Verde das Terras Baixas",
    13: "Floresta Estacional Sempre Verde Submontana",
    14: "Floresta Estacional Semidecidual Aluvial",
    15: "Floresta Estacional Semidecidual das Terras Baixas",
    16: "Floresta Estacional Semidecidual Submontana",
    17: "Floresta Estacional Semidecidual Montana",
    18: "Floresta Estacional Decidual Aluvial",
    19: "Floresta Estacional Decidual das Terras Baixas",
    20: "Floresta Estacional Decidual Submontana",
    21: "Floresta Estacional Decidual Montana",
    22: "Campinarana Florestada",
    23: "Campinarana Arborizada",
    24: "Campinarana Arbustiva",
    25: "Campinarana Gramíneo-Lenhosa",
    26: "Savana Florestada",
    27: "Savana Arborizada",
    28: "Savana Parque",
    29: "Savana Gramíneo-Lenhosa",
    30: "Savana-Estépica Florestada",
    31: "Savana-Estépica Arborizada",
    32: "Savana-Estépica Arbustiva",
    33: "Savana-Estépica Parque",
    34: "Savana-Estépica Gramíneo-Lenhosa",
    35: "Estepe Arborizada",
    36: "Estepe Parque",
    37: "Estepe Gramíneo-Lenhosa",
    38: "Formação Pioneira com influência marinha",
    39: "Formação Pioneira com influência fluviomarinha",
    40: "Formação Pioneira com influência fluvial e/ou lacustre",
    41: "Refúgio Vegetacional Submontano",
    42: "Refúgio Vegetacional Montano",
    43: "Refúgio Vegetacional Alto-Montano",
    44: "Agricultura",
    45: "Agropecuária",
    46: "Pecuária (pastagens)",
    47: "Indiscriminada",
    48: "Influência urbana",
    49: "Vegetação Secundária",
    50: "Florestamento/Reflorestamento",
    51: "Contato (Ecótono)",
    52: "Afloramento Rochoso",
    53: "Dunas",
    54: "Corpo d'água continental",
}

#: Official IBGE colours (``vege_legenda2.qml``), joined by label text — see
#: module docstring. Note 49 "Vegetação Secundária" reads as blue (``0073e1``)
#: in the source style, which looks like a water colour; that is what the
#: official style actually assigns, not a transcription slip here.
IBGE_VEG_COLOR_MAP: Dict[int, str] = {
    1: "a8ff00", 2: "73ff00", 3: "00f500", 4: "00ff73", 5: "00cd00",
    6: "d6ffa8", 7: "c0ffa8", 8: "a8ffa8", 9: "99d4e6", 10: "99c2e6",
    11: "9ccd89", 12: "51a800", 13: "007e00", 14: "e6e699", 15: "d4e699",
    16: "c2e699", 17: "becd89", 18: "cdcd89", 19: "cdbe89", 20: "a8a873",
    21: "8fa873", 22: "89cdcd", 23: "a8ffc0", 24: "a8ffeb", 25: "a8ebff",
    26: "ffa8a8", 27: "ffc0a8", 28: "ffd6a8", 29: "ffeba8", 30: "cdcd00",
    31: "e6c200", 32: "fcbc7d", 33: "ffd600", 34: "f5f500", 35: "e6d499",
    36: "e6c299", 37: "e6ae99", 38: "00ffd6", 39: "00d6ff", 40: "a8d6ff",
    41: "ff0073", 42: "ffa8ff", 43: "ffa8d6", 44: "e9e9e9", 45: "e9e9e9",
    46: "e9e9e9", 47: "b2b2b2", 48: "b2b2b2", 49: "0073e1", 50: "c9a538",
    51: "e39e00", 52: "c0a8ff", 53: "ffff00", 54: "73fff7",
}

#: ``getMapId`` vis params for the classified raster (services.layers /
#: services.ibge_vegetation). Codes are contiguous 1-54, so a plain min/max
#: palette renders every class without a remap.
IBGE_VEG_VIS = {
    "min": 1,
    "max": 54,
    "palette": [IBGE_VEG_COLOR_MAP[i] for i in range(1, 55)],
}

# --------------------------------------------------------------------------- #
# Shared natural/anthropic/forest taxonomy — the QC comparison axis
# --------------------------------------------------------------------------- #
#: Six buckets both datasets get reduced to for the comparison tab. Built once
#: so IBGE and MapBiomas 2022 are compared on the same terms rather than
#: class-by-class (the two legends don't share classes).
GROUP_NATURAL_FOREST = "natural_forest"
GROUP_NATURAL_NON_FOREST = "natural_non_forest"
GROUP_ANTHROPIC_FOREST = "anthropic_forest"
GROUP_ANTHROPIC_REGROWTH = "anthropic_regrowth"
GROUP_ANTHROPIC_NON_FOREST = "anthropic_non_forest"
GROUP_WATER = "water"
GROUP_OTHER = "other"

GROUP_ORDER = [
    GROUP_NATURAL_FOREST, GROUP_NATURAL_NON_FOREST,
    GROUP_ANTHROPIC_FOREST, GROUP_ANTHROPIC_REGROWTH,
    GROUP_ANTHROPIC_NON_FOREST, GROUP_WATER, GROUP_OTHER,
]

GROUP_LABELS_PT: Dict[str, str] = {
    GROUP_NATURAL_FOREST: "Natural — Floresta",
    GROUP_NATURAL_NON_FOREST: "Natural — Não Floresta",
    GROUP_ANTHROPIC_FOREST: "Antrópico — Floresta Plantada",
    GROUP_ANTHROPIC_REGROWTH: "Antrópico — Vegetação Secundária",
    GROUP_ANTHROPIC_NON_FOREST: "Antrópico — Agropecuária/Urbano",
    GROUP_WATER: "Água",
    GROUP_OTHER: "Outros/Sem Dados",
}

GROUP_LABELS_EN: Dict[str, str] = {
    GROUP_NATURAL_FOREST: "Natural — Forest",
    GROUP_NATURAL_NON_FOREST: "Natural — Non-Forest",
    GROUP_ANTHROPIC_FOREST: "Anthropic — Planted Forest",
    GROUP_ANTHROPIC_REGROWTH: "Anthropic — Secondary Vegetation",
    GROUP_ANTHROPIC_NON_FOREST: "Anthropic — Agriculture/Urban",
    GROUP_WATER: "Water",
    GROUP_OTHER: "Other/No Data",
}

GROUP_COLORS: Dict[str, str] = {
    GROUP_NATURAL_FOREST: "#1f8d49",
    GROUP_NATURAL_NON_FOREST: "#d6bc74",
    GROUP_ANTHROPIC_FOREST: "#7a5900",
    GROUP_ANTHROPIC_REGROWTH: "#a8d6ff",
    GROUP_ANTHROPIC_NON_FOREST: "#e974ed",
    GROUP_WATER: "#2532e4",
    GROUP_OTHER: "#999999",
}

#: IBGE leg2_id -> group. Every one of the 54 codes is assigned (no fallback
#: needed on this side) — see module docstring for the "Florestada" naming
#: convention this reading is based on.
IBGE_VEG_TO_GROUP: Dict[int, str] = {
    **{i: GROUP_NATURAL_FOREST for i in list(range(1, 23)) + [26, 30]},
    **{i: GROUP_NATURAL_NON_FOREST for i in (
        [23, 24, 25, 27, 28, 29] + list(range(31, 44)) + [51, 52, 53]
    )},
    50: GROUP_ANTHROPIC_FOREST,
    49: GROUP_ANTHROPIC_REGROWTH,
    **{i: GROUP_ANTHROPIC_NON_FOREST for i in (44, 45, 46, 47, 48)},
    54: GROUP_WATER,
}

#: MapBiomas class code (config.mapbiomas.MAPBIOMAS_LABELS_PT) -> group.
#: Deliberately partial — any class not listed here (an id introduced by a
#: future collection, or one of the rarer transition/"outra" codes) falls back
#: to GROUP_OTHER via ``.get(code, GROUP_OTHER)`` at the call site rather than
#: raising, since silently mis-bucketing a rare class is worse than an honest
#: "other". Built from MAPBIOMAS_LABELS_PT's own class families
#: (config/mapbiomas.py) — Floresta family (1,2,3,5,6,7,49) vs. natural
#: non-forest (4,8,10,11,12,13,23,28,29,32,50) vs. Silvicultura alone (9,
#: MapBiomas' only "planted forest" class — Dendê/35 is scored as a crop, not
#: forest, since it is planted for fruit not timber/canopy) vs. Agropecuária/
#: crop family (14 onward) vs. water (26,31,33,34,51,52).
MAPBIOMAS_TO_GROUP: Dict[int, str] = {
    **{i: GROUP_NATURAL_FOREST for i in (1, 2, 3, 5, 6, 7, 49)},
    **{i: GROUP_NATURAL_NON_FOREST for i in (4, 8, 10, 11, 12, 13, 23, 28, 29, 32, 50)},
    9: GROUP_ANTHROPIC_FOREST,
    **{i: GROUP_ANTHROPIC_NON_FOREST for i in (
        14, 15, 16, 17, 18, 19, 20, 21, 24, 30, 35, 36, 37, 38, 39, 40, 41,
        42, 43, 44, 45, 46, 47, 48, 62,
    )},
    **{i: GROUP_WATER for i in (26, 31, 33, 34, 51, 52)},
    **{i: GROUP_OTHER for i in (0, 22, 25, 27, 146, 435, 466)},
}


def ibge_group(leg2_id: int) -> str:
    return IBGE_VEG_TO_GROUP.get(int(leg2_id), GROUP_OTHER)


def mapbiomas_group(class_id: int) -> str:
    return MAPBIOMAS_TO_GROUP.get(int(class_id), GROUP_OTHER)
