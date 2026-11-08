"""Disturbance, fire and canopy for the world page: Hansen forest loss and MODIS burned area.

These are the global counterparts of what the Canada page gets from NTEMS stand age and the USA page
from LCMS, MTBS and Tree Canopy Cover. Only what exists everywhere is used:

* **Hansen Global Forest Change** (``UMD/hansen/global_forest_change_2025_v1_13``): ``lossyear`` 1–25 =
  2001–2025 and ``treecover2000``. *Disturbance* here is **tree-cover loss** (a stand-replacing event of
  any cause: fire, clearing, storms); the product does not say the cause. *Time since disturbance* is
  years since the last detected loss on pixels that were forest in 2000, **censored at 2001**: a stand
  never lost since then is "25 or more", never "25 years old". *Canopy* is the 2000 canopy minus the
  pixels lost since: regrowth after loss is not counted (Hansen's gain is one undated flag).
* **MODIS MCD64A1** (``MODIS/061/MCD64A1``): burned area, 500 m, monthly from 2001: the global fire
  record. It maps burned area, not severity, and small fires fall between its pixels.
"""

from __future__ import annotations

from typing import Dict, List

from . import forest as fc_cfg

HANSEN = fc_cfg.HANSEN_GFC_DATASET
LOSS_YEAR_START = fc_cfg.HANSEN_LOSS_YEAR_START
LOSS_YEAR_END = fc_cfg.HANSEN_LOSS_YEAR_END
LOSS_YEARS: List[int] = list(range(LOSS_YEAR_START, LOSS_YEAR_END + 1))

#: Canopy series: 2000 (Hansen's baseline) to the last loss year.
CANOPY_YEAR_START = 2000
CANOPY_YEAR_END = LOSS_YEAR_END
CANOPY_YEARS: List[int] = list(range(CANOPY_YEAR_START, CANOPY_YEAR_END + 1))

CHANGE_LABELS_EN: Dict[int, str] = {1: "Tree-cover loss"}
CHANGE_LABELS_PT: Dict[int, str] = {1: "Perda de cobertura arbórea"}
CHANGE_COLORS: Dict[int, str] = {1: fc_cfg.HANSEN_LOSS_COLOR}

#: Years since the last loss, as bins. The last is censored by the 2001 start.
AGE_BINS = [(0, 5, "0–5"), (6, 10, "6–10"), (11, 15, "11–15"), (16, 20, "16–20"), (21, 24, "21–24")]
AGE_CENSORED = "≥ 25 (none since 2001)"
AGE_ORDER = [b[2] for b in AGE_BINS] + [AGE_CENSORED]
AGE_COLORS = {"0–5": "#d73027", "6–10": "#f46d43", "11–15": "#fdae61", "16–20": "#a6d96a",
              "21–24": "#66bd63", AGE_CENSORED: "#1a7837"}

MODIS_BURN = "MODIS/061/MCD64A1"
BURN_YEAR_START = 2001
BURN_YEAR_END = 2025
BURN_YEARS: List[int] = list(range(BURN_YEAR_START, BURN_YEAR_END + 1))
BURN_SCALE_M = 500
BURN_LABELS_EN: Dict[int, str] = {1: "Burned area"}
BURN_LABELS_PT: Dict[int, str] = {1: "Área queimada"}
BURN_COLORS: Dict[int, str] = {1: "#d54309"}


def change_label(code: int, lang: str) -> str:
    table = CHANGE_LABELS_PT if lang == "pt" else CHANGE_LABELS_EN
    return table.get(code, f"Classe {code}" if lang == "pt" else f"Class {code}")


def severity_label(code: int, lang: str) -> str:
    """The fire class label (the world has one class, burned; the USA's severity names are gone)."""
    table = BURN_LABELS_PT if lang == "pt" else BURN_LABELS_EN
    return table.get(code, f"Classe {code}" if lang == "pt" else f"Class {code}")


#: Kept under the USA names the chart and panel code reads.
SEVERITY_COLORS = BURN_COLORS
SEVERITY_LABELS_EN = BURN_LABELS_EN
SEVERITY_LABELS_PT = BURN_LABELS_PT
