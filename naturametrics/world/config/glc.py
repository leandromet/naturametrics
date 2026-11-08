"""GLC-FCS30D annual land cover — the world's counterpart to the other pages' MapBiomas, ACI and NLCD.

One 30 m land-cover map per year, **2000–2022**, for the whole globe: the community-catalog tiles
``projects/sat-io/open-datasets/GLC-FCS30D/annual`` (961 tiles of 5° × 5°, 23 bands ``b1``…``b23``,
2000 = ``b1``). Zhang, X. et al. (2021), *GLC_FCS30D*, Earth System Science Data 13; Zenodo
doi 10.5281/zenodo.8239305. It has a fine classification (33 codes) and the same series everywhere,
so there is no "starts late" or "stops at 58°N" caveat; the page says only that it begins in 2000
and that it is a global product, less exact locally than a national map.

The module keeps the names the NLCD module had (``band_for_year``, ``label``, ``color``, the group
sets, ``STACK_PRIORITY``, ``years_for``, ``nearest_year``) so the history, chart and export code reads
the same on every page. Class names, colours and groups come from ``world/data/glc_legend.json``,
exported from muda-clima's ``glc_fcs30d`` (one legend for the suite).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

GLC_ASSET_DIR = "projects/sat-io/open-datasets/GLC-FCS30D/annual"
GLC_DATASET = GLC_ASSET_DIR
GLC_BAND = "b1"                       # kept for callers that name one band; real bands are b1..b23

GLC_YEAR_START = 2000
GLC_YEAR_END = 2022
GLC_YEARS: List[int] = list(range(GLC_YEAR_START, GLC_YEAR_END + 1))

DATA = Path(__file__).resolve().parent.parent / "data" / "glc_legend.json"


@lru_cache(maxsize=1)
def _legend() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def source_band(year: int) -> str:
    """The tile band for a year: 2000 is ``b1``."""
    return f"b{year - 1999}"


def band_for_year(year: int) -> str:
    """Band name after stacking — see ``services/glc_history.py``."""
    return f"glc_{year}"


def all_bands() -> List[str]:
    return [band_for_year(y) for y in GLC_YEARS]


def label(class_id: int, lang: str = "en") -> str:
    info = _legend()["legend"].get(str(class_id))
    if info is None:
        return f"Classe {class_id}" if lang == "pt" else f"Class {class_id}"
    return info["pt" if lang == "pt" else "en"]


def color(class_id: int) -> str:
    info = _legend()["legend"].get(str(class_id))
    return info["hex"] if info else "#cccccc"


GLC_GAP_COLOR = "cccccc"
#: Dense 0..255 palette for ``getMapId`` (the same as muda-clima's).
GLC_PALETTE: List[str] = _legend()["palette"].split(",")
GLC_VIS = {"min": 0, "max": 255, "palette": GLC_PALETTE}

# --------------------------------------------------------------------------- #
# Class groups — same names as the other pages', so shared code keeps working.
# --------------------------------------------------------------------------- #
FOREST = frozenset({51, 52, 61, 62, 71, 72, 81, 82, 91, 92})
WETLAND = frozenset({180, 181, 182, 183, 184})
GRASS_SHRUB = frozenset({120, 121, 122, 130, 140, 150, 152, 153})
WATER = frozenset({210})
BARREN = frozenset({200, 201, 202, 220})        # bare ground, and permanent ice and snow
BURNT: frozenset = frozenset()                   # GLC has no burnt-area class
URBAN = frozenset({190})
NO_DATA: frozenset = frozenset()
CROPLAND = frozenset({10, 11, 12, 20})

NATURAL_VEGETATION = FOREST | WETLAND | GRASS_SHRUB

STACK_PRIORITY: List[int] = (
    sorted(FOREST) + sorted(WETLAND) + sorted(GRASS_SHRUB) + sorted(BARREN)
)

#: No place is left without a land-cover series (the region idea belonged to Alaska and Hawaii).
NO_LANDCOVER: frozenset = frozenset()


def years_for(region: str = "world") -> List[int]:
    """The GLC years: the same series everywhere."""
    return GLC_YEARS


def nearest_year(region: str, year: int) -> int:
    """A requested year snapped to one the series has."""
    return min(GLC_YEARS, key=lambda y: abs(y - year))
