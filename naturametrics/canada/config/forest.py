"""Forest age and forest change for Canada — NTEMS and Hansen GFC.

Canada's counterpart to :mod:`naturametrics.config.vegetation_age`, and a
better-founded one. Brazil has to *derive* stand age by counting years a pixel
stayed vegetated in the MapBiomas DSV series, and the derivation carries a
censoring ceiling because the series only starts in 1985. Canada does not need
that: NTEMS publishes a **measured** forest-age raster.

Verified against the assets on 2026-08-21.

**NTEMS forest age.** ``CANADA/NFIS/NTEMS/CA_FOREST_AGE`` is an ImageCollection
holding exactly one image (index ``2019``) with one band, ``forest``, giving
stand age in years as of 2019. Two properties matter:

* It must be read through ``.mosaic()``. Sampling ``.first()`` directly returns
  null everywhere — the collection's single image does not resolve to a plain
  Image the way ``ee.Image(asset)`` would.
* It is **masked to forested pixels**. A null is "not forest here", not "no
  data" — which is exactly the semantics the summary panel wants, and why the
  non-forest share is reported rather than silently dropped.

Sampled ages: 98 y at 53.5°N/-122.2 (BC interior), 86 y in northern Ontario,
42 y in Québec, 52 y in boreal Alberta, null in downtown Kelowna.

**Hansen Global Forest Change.** ``UMD/hansen/global_forest_change_2025_v1_13``
— global, so it answers everywhere in Canada including north of the ACI limit.
``lossyear`` is 1..25 meaning 2001..2025; ``treecover2000`` is percent canopy in
2000; ``gain`` is a 0/1 flag over the whole record rather than a dated series,
which is why the change panel reports gain as a single total and only loss gets
a year.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# NTEMS forest age
# --------------------------------------------------------------------------- #

NTEMS_AGE_DATASET = "CANADA/NFIS/NTEMS/CA_FOREST_AGE"
NTEMS_AGE_BAND = "forest"

#: The year the published raster describes. Ages are "as of" this year, so a
#: stand reported as 40 y old is ~46 y old in 2025 — the UI says so rather than
#: quietly ageing the numbers forward, which would be inventing precision.
NTEMS_AGE_REFERENCE_YEAR = 2019

#: Reporting bins for the age histogram. Round numbers, a display choice rather
#: than a derived quantity — same rationale as Brazil's AGE_BIN_EDGES.
AGE_BIN_EDGES: List[Tuple[int, int, str]] = [
    (0, 20, "0–20"),
    (21, 40, "21–40"),
    (41, 60, "41–60"),
    (61, 80, "61–80"),
    (81, 100, "81–100"),
    (101, 150, "101–150"),
    (151, 10_000, "150+"),
]

#: Light→dark green ramp, youngest→oldest. Unlike Brazil there is no "censored"
#: bin to colour differently: NTEMS reports a real age for every forest pixel,
#: so the ramp runs the whole way without a special case.
AGE_BIN_COLORS: Dict[str, str] = {
    "0–20": "#d9f0a3",
    "21–40": "#addd8e",
    "41–60": "#78c679",
    "61–80": "#41ab5d",
    "81–100": "#238443",
    "101–150": "#006837",
    "150+": "#004529",
}

AGE_BIN_ORDER: List[str] = [b[2] for b in AGE_BIN_EDGES]


def age_bin(age: float) -> str:
    """Which reporting bin an age value falls into."""
    for lo, hi, name in AGE_BIN_EDGES:
        if lo <= age <= hi:
            return name
    return AGE_BIN_EDGES[-1][2]


def age_bin_color(name: str) -> str:
    return AGE_BIN_COLORS.get(name, "#cccccc")


#: Map visualisation for the age layer. 0–200 rather than the raster's true max:
#: the tail above 200 y is thin, and stretching to it would flatten every
#: distinction in the range where most of Canada's forest actually sits.
NTEMS_AGE_VIS = {
    "min": 0,
    "max": 200,
    "palette": ["d9f0a3", "addd8e", "78c679", "41ab5d", "238443",
                "006837", "004529"],
}

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
