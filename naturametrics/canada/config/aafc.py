"""AAFC Annual Crop Inventory — class labels, colours and palette.

Canada's counterpart to :mod:`naturametrics.config.mapbiomas`. Labels and the
colour map are ported from Yvynation's ``config.py`` (the published AAFC legend);
Portuguese labels are added here because this app is bilingual and the ACI legend
is only distributed in English/French.

**Two coverage facts shape the whole Canada page, and both are properties of the
product rather than of this code — verified against the asset on 2026-08-21:**

1. **Years.** ``AAFC/ACI`` holds 2009–2025. 2009 and 2010 cover the Prairies
   only (AB/SK/MB); national coverage starts in **2011**. A buffer in Ontario
   therefore has no 2009 column, and that is data, not a bug.
2. **Northern limit.** The inventory stops at roughly **54–58°N**, ragged and
   longitude-dependent — it is an *agricultural* inventory, not a national land
   cover. Sampled: data at 55°N/-106, none at 57°N/-106; data to ~58°N at
   -120. The northern majority of Canada's landmass has no ACI pixel at all.

Consequence for the UI: unlike Brazil (where a click outside MapBiomas' extent
is refused), a click north of the ACI limit is **allowed** — the forest-age and
Hansen panels answer everywhere — and only the land-cover panel reports that it
has nothing to show. See ``canada/services/geo.py``.
"""

from __future__ import annotations

from typing import Dict, List

# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #

AACI_DATASET = "AAFC/ACI"

#: Every year the collection holds.
ACI_YEAR_START = 2009
ACI_YEAR_END = 2025
ACI_YEARS: List[int] = list(range(ACI_YEAR_START, ACI_YEAR_END + 1))

#: First year with coverage outside the Prairies. Before this the inventory is
#: AB/SK/MB only — surfaced in the UI rather than left for the user to infer
#: from a chart that starts two columns late.
ACI_NATIONAL_FROM = 2011

#: Approximate northern edge of the inventory, for the "no data up here" notice.
#: Ragged in reality (see module docstring); this is the value the copy quotes.
ACI_NORTH_LIMIT_LAT = 58.0

#: The single band each yearly image carries.
ACI_BAND = "landcover"


def band_for_year(year: int) -> str:
    """Band name after stacking — see ``services/aci_history.py``.

    The ACI is an ImageCollection of one image per year, not MapBiomas' single
    40-band image, so the history query renames each year's ``landcover`` band
    to this before ``ee.Image.cat``. That restores the one-round-trip shape the
    Brazil path uses.
    """
    return f"aci_{year}"


def all_bands() -> List[str]:
    return [band_for_year(y) for y in ACI_YEARS]


# --------------------------------------------------------------------------- #
# Class labels
# --------------------------------------------------------------------------- #

ACI_LABELS_EN: Dict[int, str] = {
    10: "Cloud", 20: "Water", 30: "Exposed Land and Barren",
    34: "Urban and Developed", 35: "Greenhouses", 50: "Shrubland",
    60: "Forest Fire and Burnt Area", 80: "Wetland", 85: "Peatland",
    110: "Grassland", 120: "Agriculture (undifferentiated)", 121: "Cropland",
    122: "Pasture and Forages", 130: "Too Wet to be Seeded", 131: "Fallow",
    132: "Cereals", 133: "Barley", 134: "Other Grains", 135: "Millet",
    136: "Oats", 137: "Rye", 138: "Spelt", 139: "Triticale", 140: "Wheat",
    141: "Switchgrass", 142: "Sorghum", 143: "Quinoa", 145: "Winter Wheat",
    146: "Spring Wheat", 147: "Corn for Grain", 148: "Tobacco", 149: "Ginseng",
    150: "Oilseeds", 151: "Borage", 152: "Camelina",
    153: "Canola and Rapeseed", 154: "Flaxseed", 155: "Mustard",
    156: "Safflower", 157: "Sunflower", 158: "Soybeans", 159: "Other Oilseeds",
    160: "Pulses", 161: "Other Pulses", 162: "Peas", 163: "Chickpeas",
    167: "Beans", 168: "Fababeans", 174: "Lentils", 175: "Vegetables",
    176: "Tomatoes", 177: "Potatoes", 178: "Sugarbeets", 179: "Other Vegetables",
    180: "Fruits", 181: "Berries", 182: "Blueberry", 183: "Cranberry",
    185: "Other Berries", 188: "Orchards", 189: "Other Fruits",
    190: "Vineyards", 191: "Hops", 192: "Sod", 193: "Herbs", 194: "Nursery",
    195: "Buckwheat", 196: "Canaryseed", 197: "Hemp", 198: "Vetch",
    199: "Other Crops", 200: "Forest (undifferentiated)", 210: "Coniferous",
    220: "Broadleaf", 230: "Mixedwood",
}

ACI_LABELS_PT: Dict[int, str] = {
    10: "Nuvem", 20: "Água", 30: "Solo exposto e estéril",
    34: "Área urbana e construída", 35: "Estufas", 50: "Vegetação arbustiva",
    60: "Incêndio florestal e área queimada", 80: "Área úmida",
    85: "Turfeira", 110: "Campo natural",
    120: "Agropecuária (indiferenciada)", 121: "Lavoura",
    122: "Pastagem e forrageiras", 130: "Encharcado demais para semear",
    131: "Pousio", 132: "Cereais", 133: "Cevada", 134: "Outros grãos",
    135: "Milheto", 136: "Aveia", 137: "Centeio", 138: "Espelta",
    139: "Triticale", 140: "Trigo", 141: "Capim-varredura",
    142: "Sorgo", 143: "Quinoa", 145: "Trigo de inverno",
    146: "Trigo de primavera", 147: "Milho em grão", 148: "Tabaco",
    149: "Ginseng", 150: "Oleaginosas", 151: "Borragem", 152: "Camelina",
    153: "Canola e colza", 154: "Linhaça", 155: "Mostarda", 156: "Cártamo",
    157: "Girassol", 158: "Soja", 159: "Outras oleaginosas",
    160: "Leguminosas", 161: "Outras leguminosas", 162: "Ervilha",
    163: "Grão-de-bico", 167: "Feijão", 168: "Fava", 174: "Lentilha",
    175: "Hortaliças", 176: "Tomate", 177: "Batata", 178: "Beterraba açucareira",
    179: "Outras hortaliças", 180: "Frutas", 181: "Frutas vermelhas",
    182: "Mirtilo", 183: "Cranberry", 185: "Outras frutas vermelhas",
    188: "Pomares", 189: "Outras frutas", 190: "Vinhedos", 191: "Lúpulo",
    192: "Grama cultivada", 193: "Ervas aromáticas", 194: "Viveiro",
    195: "Trigo-sarraceno", 196: "Alpiste", 197: "Cânhamo", 198: "Ervilhaca",
    199: "Outras culturas", 200: "Floresta (indiferenciada)",
    210: "Conífera", 220: "Folhosa", 230: "Floresta mista",
}

ACI_LABELS: Dict[str, Dict[int, str]] = {
    "en": ACI_LABELS_EN,
    "pt": ACI_LABELS_PT,
}


def label(class_id: int, lang: str = "en") -> str:
    """Human label for an ACI class code, falling back to the code itself."""
    table = ACI_LABELS.get(lang, ACI_LABELS_EN)
    return table.get(
        class_id, f"Classe {class_id}" if lang == "pt" else f"Class {class_id}"
    )


# --------------------------------------------------------------------------- #
# Colours
# --------------------------------------------------------------------------- #
# The official AAFC legend colours. Like MapBiomas' palette these are prescribed
# and not colour-blind safe, so the legend always pairs swatch with label.

ACI_COLOR_MAP: Dict[int, str] = {
    10: "#000000", 20: "#3333ff", 30: "#996666", 34: "#cc6699", 35: "#e1e1e1",
    50: "#ffff00", 60: "#666666", 80: "#993399", 85: "#501b50", 110: "#cccc00",
    120: "#cc6600", 121: "#ff9933", 122: "#ffcc33", 130: "#7899f6",
    131: "#ff9900", 132: "#660000", 133: "#dae31d", 134: "#99cc00",
    135: "#d2db25", 136: "#d1d52b", 137: "#cacd32", 138: "#c3c63a",
    139: "#b9bc44", 140: "#a7b34d", 141: "#b9c64e", 142: "#999900",
    143: "#e9e2b1", 145: "#809769", 146: "#92a55b", 147: "#ffff99",
    148: "#98887c", 149: "#799b93", 150: "#5ea263", 151: "#52ae77",
    152: "#41bf7a", 153: "#d6ff70", 154: "#8c8cff", 155: "#d6cc00",
    156: "#ff7f00", 157: "#315491", 158: "#cc9933", 159: "#5ea296",
    160: "#896e43", 161: "#996633", 162: "#8f6c3d", 163: "#b6a472",
    167: "#82654a", 168: "#a39069", 174: "#b85900", 175: "#b74b15",
    176: "#ff8a8a", 177: "#ffcccc", 178: "#6f55ca", 179: "#ffccff",
    180: "#dc5424", 181: "#d05a30", 182: "#d20000", 183: "#cc0000",
    185: "#dc3200", 188: "#ff6666", 189: "#c5453b", 190: "#7442bd",
    191: "#ffcc99", 192: "#b5fb05", 193: "#ccff05", 194: "#07f98c",
    195: "#00ffcc", 196: "#cc33cc", 197: "#8e7672", 198: "#b1954f",
    199: "#749a66", 200: "#009900", 210: "#006600", 220: "#00cc00",
    230: "#cc9900",
}

#: Fill for codes with no assigned swatch, so gaps read as gaps.
ACI_GAP_COLOR = "cccccc"

#: Dense 0..230 palette for ``getMapId``. Earth Engine needs one entry per index
#: across the whole min..max range, and ACI codes are sparse (10, 20, 30, 34…),
#: so unmapped indices get the gap colour.
ACI_PALETTE: List[str] = [
    ACI_COLOR_MAP[i].lstrip("#") if i in ACI_COLOR_MAP else ACI_GAP_COLOR
    for i in range(231)
]

ACI_VIS = {"min": 0, "max": 230, "palette": ACI_PALETTE}


def color(class_id: int) -> str:
    """Hex colour (with ``#``) for a class code."""
    return ACI_COLOR_MAP.get(class_id, f"#{ACI_GAP_COLOR}")


# --------------------------------------------------------------------------- #
# Class groups
# --------------------------------------------------------------------------- #
# Unlike MapBiomas' groups (still provisional — see D6 in doc/09), these come
# straight off the published legend's own top-level structure: the ACI encodes
# its hierarchy in the numbering, so "which codes are forest" is read from the
# legend rather than inferred.

FOREST = frozenset({200, 210, 220, 230})
WETLAND = frozenset({80, 85})
GRASS_SHRUB = frozenset({50, 110})
WATER = frozenset({20})
BARREN = frozenset({30})
BURNT = frozenset({60})
URBAN = frozenset({34, 35})
NO_DATA = frozenset({10})

#: Everything from "Agriculture (undifferentiated)" up to "Other Crops" — the
#: cultivated block of the legend, which is the bulk of the class list.
CROPLAND = frozenset(
    c for c in ACI_LABELS_EN if 120 <= c <= 199
)

#: Natural cover: forest + wetland + grass/shrub. Deliberately excludes burnt
#: area (a disturbance state, not a cover type) and cropland/pasture.
NATURAL_VEGETATION = FOREST | WETLAND | GRASS_SHRUB

#: Stacking order for the history chart, mirroring the Brazil convention:
#: natural formations at the bottom, anthropic above, water and no-data last.
STACK_PRIORITY: List[int] = (
    sorted(FOREST) + sorted(WETLAND) + sorted(GRASS_SHRUB) + sorted(BARREN)
    + sorted(BURNT)
)
