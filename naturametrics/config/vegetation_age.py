"""MapBiomas Deforestation & Secondary Vegetation (DSV) product — forest-age input.

**Decision (2026-08-19), see doc/10-forest-age.md §3 E1.** The reference script the
user pointed us at (``doc/mapbiomas_veg_secundaria.js``) is MapBiomas' own *generator*
for this classification: it reads ``projects/mapbiomas-workspace/COLECAO9/integracao``
(an internal MapBiomas Earth Engine asset — confirmed unreadable by this service
account, and a Collection 9 vintage besides, one behind the 10.1 used everywhere else
in this app) and derives, year by year, whether each pixel is stable primary
vegetation, stable secondary vegetation, or mid-transition.

MapBiomas separately **publishes that derivation's own output** as a public asset,
already validated and consolidated: :data:`DSV_ASSET` below. Re-deriving the rule
engine ourselves would mean reimplementing ~300 lines of temporal-window pattern
matching against an asset we cannot read, to reproduce a result MapBiomas already
computed and ships. So the "python version using Earth Engine tools" of the reference
script that this app implements is not the *classification* stage (already done,
upstream) — it is the **age-from-classification** stage: turning the year-by-year
class codes below into a running "years since last disturbance" count. That logic has
no MapBiomas equivalent asset and is what ``services/vegetation_age.py`` computes.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

DSV_ASSET = (
    "projects/mapbiomas-public/assets/brazil/lulc/collection10_1/"
    "mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3"
)

#: The DSV product's own window rules need a few years of lookback/lookahead, so it
#: starts two years later than the 1985 coverage series and, as of this writing, has
#: not yet caught up to the current coverage series' last year either.
DSV_YEAR_START = 1987
DSV_YEAR_END = 2024
DSV_YEARS: List[int] = list(range(DSV_YEAR_START, DSV_YEAR_END + 1))


def dsv_band_for_year(year: int) -> str:
    return f"classification_{year}"


# --------------------------------------------------------------------------- #
# Class codes — ported from the ``legendDeforestation`` table in the reference
# script, which is itself MapBiomas' published legend for this product.
# --------------------------------------------------------------------------- #

DSV_LABELS_PT: Dict[int, str] = {
    0: "Sem informação",
    1: "Antrópico",
    2: "Vegetação primária",
    3: "Vegetação secundária",
    4: "Supressão de vegetação primária",
    5: "Recuperação de vegetação secundária",
    6: "Supressão de vegetação secundária",
    7: "Outras transições",
}

DSV_LABELS_EN: Dict[int, str] = {
    0: "No data",
    1: "Anthropic",
    2: "Primary vegetation",
    3: "Secondary vegetation",
    4: "Primary vegetation suppression",
    5: "Secondary vegetation regrowth",
    6: "Secondary vegetation suppression",
    7: "Other transitions",
}


def dsv_label(class_id: int | None, lang: str = "pt") -> str:
    if class_id is None:
        return "Sem dado" if lang == "pt" else "No data"
    table = DSV_LABELS_PT if lang == "pt" else DSV_LABELS_EN
    return table.get(int(class_id), f"Classe {class_id}")


#: Same palette as the reference script's ``transitionsPalette`` — carried over
#: deliberately (not the MapBiomas coverage palette) so this chart reads as its own
#: thing rather than a variant of the land-use history above it.
DSV_COLORS: Dict[int, str] = {
    0: "#ffffff",
    1: "#faf5d1",
    2: "#3f7849",
    3: "#5bcf20",
    4: "#ea1c1c",
    5: "#b4f792",
    6: "#fe9934",
    7: "#303149",
}


def dsv_color(class_id: int | None) -> str:
    if class_id is None:
        return "#cccccc"
    return DSV_COLORS.get(int(class_id), "#999999")


# --------------------------------------------------------------------------- #
# Age classes produced by the sequential counter in services/vegetation_age.py
# --------------------------------------------------------------------------- #
#: A pixel's age counter climbs by one every year it is class 2 or 3 (stable
#: vegetation), resets to 0 on a suppression event (4 or 6) or when the year is
#: anthropic/no-data/noise (1, 0, 7), and restarts at 1 on a regrowth event (5) — the
#: year the DSV product records the forest as having re-established. See
#: ``_forest_age_bands`` for why this is a correct read of the class codes above and
#: how it reproduces "censored" without a separate flag.
CENSORED_AGE = len(DSV_YEARS)  # age reached only by a pixel that was class 2 every year

#: Round-number reporting bins for the *dated* part of the distribution — i.e.
#: everything below CENSORED_AGE. These are a display choice (doc/10 §6), not a
#: derived quantity, so hard-coding the edges is fine; only CENSORED_AGE itself must
#: track the data.
AGE_BIN_EDGES: List[Tuple[int, int, str]] = [
    (1, 5, "0–5 anos"),
    (6, 10, "6–10 anos"),
    (11, 20, "11–20 anos"),
    (21, 30, "21–30 anos"),
    (31, CENSORED_AGE - 1, "31+ anos (datado)"),
]


def censored_label(lang: str = "pt") -> str:
    if lang == "pt":
        return f"≥ {CENSORED_AGE} (natural desde {DSV_YEAR_START})"
    return f"≥ {CENSORED_AGE} years (no change observed since {DSV_YEAR_START})"


def age_bin(age: int) -> str:
    """Which reporting bin an age value falls into, including the censored bin."""
    if age >= CENSORED_AGE:
        return censored_label()
    for lo, hi, name in AGE_BIN_EDGES:
        if lo <= age <= hi:
            return name
    return "0–5 anos"


#: Sequential colour ramp for the dated bins (light→dark green, youngest→oldest),
#: plus a distinct, non-ramp colour for censored — doc/10 §6 is explicit that a
#: continuous ramp must not run off the end into the censored class, since that
#: reads as "even older" rather than "unknown, possibly far older".
AGE_BIN_COLORS: Dict[str, str] = {
    "0–5 anos": "#c9e8b8",
    "6–10 anos": "#9ed17e",
    "11–20 anos": "#6cb84d",
    "21–30 anos": "#3f8f2a",
    "31+ anos (datado)": "#1f5c14",
}
CENSORED_COLOR = "#264653"
