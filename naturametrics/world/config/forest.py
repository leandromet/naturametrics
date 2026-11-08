"""Forest change for the USA page — Hansen Global Forest Change.

The Canada page also carries NTEMS stand age; that raster is Canadian and the
US has no equivalent in the catalog this page uses, so there is no age panel here.

**Hansen Global Forest Change.** ``UMD/hansen/global_forest_change_2025_v1_13`` is
global. ``lossyear`` is 1..25 meaning 2001..2025; ``treecover2000`` is percent
canopy in 2000; ``gain`` is a 0/1 flag over the whole record rather than a dated
series, which is why the change panel reports gain as a single total and only loss
gets a year.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Hansen Global Forest Change
# --------------------------------------------------------------------------- #

HANSEN_GFC_DATASET = "UMD/hansen/global_forest_change_2025_v1_13"

#: ``lossyear`` encodes 1..N as 2001..2000+N.
HANSEN_LOSS_YEAR_START = 2001
HANSEN_LOSS_YEAR_END = 2025

#: **Gain covers 2000–2012 only, and is frozen.** Per the dataset documentation:
#: "Forest gain during the period 2000-2012, defined as the inverse of loss…
#: Note that this has not been updated in subsequent versions." Confirmed
#: empirically too — ``gain`` is a strict {0,1} bitmask with no year dimension,
#: while ``lossyear`` spans 1..25.
#:
#: Two consequences the UI must respect, or it will mislead:
#:
#: 1. Gain cannot be plotted as an annual series. There is no year to plot it
#:    against, and manufacturing one would be inventing data.
#: 2. Gain must **not** be netted against loss over the full 2001–2025 record.
#:    That compares a 13-year gain figure with a 25-year loss figure. Any net
#:    has to be taken over the overlapping window below, and said to be so.
HANSEN_GAIN_YEAR_START = 2000
HANSEN_GAIN_YEAR_END = 2012

#: ``lossyear`` code for the last year gain covers — the cut for the comparable
#: window (2001..2012 inclusive).
HANSEN_GAIN_WINDOW_LOSS_CODE = HANSEN_GAIN_YEAR_END - HANSEN_LOSS_YEAR_START + 1

#: Percent canopy cover in 2000 at or above which a pixel counts as forest for
#: the loss/gain accounting. Matches the Brazil app's
#: ``settings.HANSEN_TREECOVER_THRESHOLD`` default so the two pages agree on
#: what "forest" means wherever they both use Hansen.
HANSEN_TREECOVER_THRESHOLD = 30

HANSEN_LOSS_COLOR = "#d4271e"
HANSEN_GAIN_COLOR = "#02d659"
HANSEN_FOREST_COLOR = "#1f8d49"

HANSEN_CHANGE_COLORS: Dict[str, str] = {
    "loss": HANSEN_LOSS_COLOR,
    "gain": HANSEN_GAIN_COLOR,
    "forest": HANSEN_FOREST_COLOR,
}

#: Tree-cover layer visualisation.
HANSEN_TREECOVER_VIS = {
    "min": 0,
    "max": 100,
    "palette": ["ffffff", "d9f0a3", "78c679", "238443", "004529"],
}
