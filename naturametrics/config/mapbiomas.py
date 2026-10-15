"""MapBiomas collections, class labels, colours and palette for this app.

The tables themselves live in :mod:`.mapbiomas_legend` — the suite's shared,
hash-checked legend (official Collection 11 names and colours). This module keeps
the names the rest of the app already uses (``MAPBIOMAS_*``, ``label``, ``color``)
and adds the app's own class groups below.

Collection 11 (1985–2025) is the default; older collections stay available for
comparison work, each with its own year range in ``mapbiomas_legend.YEARS``.
"""

from __future__ import annotations

from typing import Dict, List

from . import mapbiomas_legend as _legend

# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #

MAPBIOMAS_COLLECTIONS: Dict[str, str] = _legend.COLLECTIONS
MAPBIOMAS_DEFAULT_COLLECTION = _legend.DEFAULT_COLLECTION

#: The default collection's years: ``classification_1985`` … ``_2025``.
MAPBIOMAS_YEAR_START, MAPBIOMAS_YEAR_END = _legend.YEARS[MAPBIOMAS_DEFAULT_COLLECTION]
MAPBIOMAS_YEARS: List[int] = _legend.years(MAPBIOMAS_DEFAULT_COLLECTION)

band_for_year = _legend.band_for_year


def all_bands() -> List[str]:
    """Every classification band — the basis of the batched history query.

    See doc/06-ee-layers.md §4: selecting all of these and reducing once is what
    turns 41 sequential round-trips into one.
    """
    return [band_for_year(y) for y in MAPBIOMAS_YEARS]


# --------------------------------------------------------------------------- #
# Labels and colours (shared legend)
# --------------------------------------------------------------------------- #

MAPBIOMAS_LABELS_PT: Dict[int, str] = _legend.LABELS_PT
MAPBIOMAS_LABELS_EN: Dict[int, str] = _legend.LABELS_EN
MAPBIOMAS_LABELS: Dict[str, Dict[int, str]] = _legend.LABELS
MAPBIOMAS_COLOR_MAP: Dict[int, str] = _legend.COLORS
#: Fill colour for codes with no assigned swatch, so gaps are visible as gaps.
MAPBIOMAS_GAP_COLOR = _legend.GAP_COLOR
#: Dense 0..91 palette for ``getMapId`` (one entry per index up to the highest code).
MAPBIOMAS_PALETTE: List[str] = _legend.PALETTE
MAPBIOMAS_VIS = _legend.VIS

label = _legend.label
color = _legend.color


# --------------------------------------------------------------------------- #
# Class groups  —  PROVISIONAL, see D6
# --------------------------------------------------------------------------- #
#: The vegetation-age estimator (Phase 3) depends entirely on these groups, and
#: they have NOT yet been validated against the official Collection 11 legend
#: document. Three sub-questions are still open (see D6 in
#: doc/09-open-decisions.md): whether Savanna Formation counts as forest, how
#: Mosaic of Uses is treated, and confirming Forest Plantation never pools into
#: natural vegetation.
#:
#: Nothing in Phase 0–2 reads these. Do not let Phase 3 code consume them while
#: LEGEND_VALIDATED is False.
LEGEND_VALIDATED = False

FOREST_FORMATIONS = frozenset({3, 5, 6, 49})          # closed-canopy natural forest
SAVANNA_FORMATIONS = frozenset({4, 7})                # cerrado sensu stricto + C11 flooded savanna
NATURAL_NON_FOREST = frozenset({10, 11, 12, 13, 29, 32, 50, 77, 84})  # 77 = the old 13 in C11
PLANTED_FOREST = frozenset({9})                       # never pooled into "natural"
WATER = frozenset({26, 33, 34, 31})
NO_DATA = frozenset({0, 27})

#: Natural vegetation = forest + savanna + natural non-forest. Savanna is
#: included here but excluded from FOREST_FORMATIONS by default.
NATURAL_VEGETATION = FOREST_FORMATIONS | SAVANNA_FORMATIONS | NATURAL_NON_FOREST
