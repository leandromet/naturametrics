"""USFS LCMS (Landscape Change Monitoring System), MTBS and NLCD Tree Canopy Cover for the USA page.

These are the American counterparts of what the Canada page gets from NTEMS stand age: *when* the
tree cover of a place was last disturbed, by what, and how much canopy it has. The US has no
measured stand-age raster in Earth Engine, so "age" is **time since the last detected loss**,
censored at 1985 (a stand never disturbed since then is "1985 or older", not "40 years old").

Verified in Earth Engine 2026-11-04:

* **LCMS** ``projects/gtac-data-publish/assets/LCMS/Product_Version/2025-11`` — one image per year
  and study area (``CONUS``, ``AK`` (southeast Alaska), ``HI``, ``PRUSVI``), 1985–2025, 30 m, bands
  ``Change``, ``Land_Cover``, ``Land_Use`` …  (the 2024-10 version is deprecated.)
* **MTBS** ``USFS/GTAC/MTBS/annual_burn_severity_mosaics/v1`` — one image per region and year,
  index ``mtbs_<REGION>_<year>``, band ``Severity`` (1984–2025 CONUS, to 2024 AK, a few years HI).
  MTBS maps only fires of at least 1 000 acres (500 in the east).
* **Tree Canopy Cover** ``projects/gtac-data-publish/assets/TCC/Product_Version/2025-6`` — 1985–2025,
  band ``NLCD_Percent_Tree_Canopy_Cover`` (0–100).
"""

from __future__ import annotations

from typing import Dict, List

LCMS = "projects/gtac-data-publish/assets/LCMS/Product_Version/2025-11"
LCMS_STUDY_AREA = {"conus": "CONUS", "ak": "AK", "hi": "HI"}
LCMS_YEAR_START, LCMS_YEAR_END = 1985, 2025
LCMS_YEARS: List[int] = list(range(LCMS_YEAR_START, LCMS_YEAR_END + 1))

#: LCMS ``Change`` classes (values 1–16). 14 is gain, 15 stable, 16 not processed.
CHANGE_LABELS_EN: Dict[int, str] = {
    1: "Wind", 2: "Hurricane", 3: "Snow or ice transition", 4: "Desiccation", 5: "Inundation",
    6: "Prescribed fire", 7: "Wildfire", 8: "Mechanical land transformation", 9: "Tree removal",
    10: "Defoliation", 11: "Southern pine beetle", 12: "Insect, disease or drought stress",
    13: "Other loss", 14: "Vegetation successional growth",
}
CHANGE_LABELS_PT: Dict[int, str] = {
    1: "Vento", 2: "Furacão", 3: "Transição de neve ou gelo", 4: "Dessecação", 5: "Inundação",
    6: "Fogo prescrito", 7: "Incêndio florestal", 8: "Transformação mecânica do terreno",
    9: "Remoção de árvores", 10: "Desfolha", 11: "Besouro-do-pinheiro-do-sul",
    12: "Insetos, doenças ou seca", 13: "Outra perda", 14: "Crescimento sucessional da vegetação",
}
CHANGE_COLORS: Dict[int, str] = {
    1: "#ff09f3", 2: "#541aff", 3: "#e4f5fd", 4: "#cc982e", 5: "#0adaff", 6: "#a10018", 7: "#d54309",
    8: "#fafa4b", 9: "#afde1c", 10: "#ffc80d", 11: "#a64c28", 12: "#f39268", 13: "#c291d5",
    14: "#00a398",
}
LOSS_CLASSES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
#: Losses that remove or damage trees. Snow/ice transition, desiccation and inundation (3–5) are
#: reported in the history but do not reset the "time since disturbance" clock.
TREE_DISTURBANCE = (1, 2, 6, 7, 8, 9, 10, 11, 12, 13)
GAIN_CLASS = 14

#: Years since the last disturbance, as bins. The last one is censored by the 1985 start.
AGE_BINS = [(0, 5, "0–5"), (6, 10, "6–10"), (11, 20, "11–20"), (21, 30, "21–30"),
            (31, 40, "31–40")]
AGE_CENSORED = "≥ 41 (none since 1985)"
AGE_ORDER = [b[2] for b in AGE_BINS] + [AGE_CENSORED]
AGE_COLORS = {"0–5": "#d73027", "6–10": "#f46d43", "11–20": "#fdae61", "21–30": "#a6d96a",
              "31–40": "#66bd63", AGE_CENSORED: "#1a7837"}

MTBS = "USFS/GTAC/MTBS/annual_burn_severity_mosaics/v1"
MTBS_REGION = {"conus": "CONUS", "ak": "AK", "hi": "HI"}
SEVERITY_LABELS_EN = {1: "Unburned to low", 2: "Low", 3: "Moderate", 4: "High", 5: "Increased greenness"}
SEVERITY_LABELS_PT = {1: "Não queimado a baixa", 2: "Baixa", 3: "Moderada", 4: "Alta",
                      5: "Aumento de verdor"}
SEVERITY_COLORS = {1: "#006400", 2: "#7fffd4", 3: "#ffff00", 4: "#ff0000", 5: "#7fff00"}

TCC = "projects/gtac-data-publish/assets/TCC/Product_Version/2025-6"
TCC_BAND = "NLCD_Percent_Tree_Canopy_Cover"
TCC_YEAR_START, TCC_YEAR_END = 1985, 2025


def change_label(code: int, lang: str) -> str:
    table = CHANGE_LABELS_PT if lang == "pt" else CHANGE_LABELS_EN
    return table.get(code, f"Classe {code}" if lang == "pt" else f"Class {code}")


def severity_label(code: int, lang: str) -> str:
    table = SEVERITY_LABELS_PT if lang == "pt" else SEVERITY_LABELS_EN
    return table.get(code, f"Classe {code}" if lang == "pt" else f"Class {code}")
