"""Base maps for the Canada page.

The plain XYZ basemaps are imported wholesale from the Brazil page's
:mod:`naturametrics.config.datasets` — Google/Esri/OSM are global and there is
no reason for two copies of the same seven URLs.

What differs is the Earth-Engine-backed imagery. Brazil has the SPOT 2008
mosaics, which are a single-year Brazilian dataset with no Canadian equivalent.
Canada gets something better-suited in its place: **annual Landsat composites**
(``LANDSAT/COMPOSITES/C02/T1_L2_ANNUAL``, verified 2026-08-21) — 1984–2026, one
cloud-free composite per year, global coverage confirmed as far north as Iqaluit
(63.75°N). Where SPOT is one snapshot to toggle on, this is a 43-year series the
user can scrub through, which is a strictly richer base layer.

Bands are named ``blue, green, red, nir, swir1, swir2, thermal`` (not Collection-2
``SR_B*`` ids) and carry scaled reflectance in roughly 0–1, so the vis ranges
below are reflectance rather than DN.
"""

from __future__ import annotations

from typing import Any, Dict

from ...config.datasets import BASEMAPS  # noqa: F401  (re-exported unchanged)

# --------------------------------------------------------------------------- #
# Landsat annual composites
# --------------------------------------------------------------------------- #

LANDSAT_ANNUAL_DATASET = "LANDSAT/COMPOSITES/C02/T1_L2_ANNUAL"

LANDSAT_YEAR_START = 1984
LANDSAT_YEAR_END = 2026

LANDSAT_ATTRIBUTION = (
    "Landsat annual composites — USGS/NASA, Collection 2 Tier 1 L2"
)

#: The two renderings offered, mirroring SPOT's visual/false-colour pair.
#: ``max`` is 0.3 for true colour because vegetated land sits well below 1.0 in
#: surface reflectance — stretching to 1.0 renders most of Canada near-black.
LANDSAT_RENDERINGS: Dict[str, Dict[str, Any]] = {
    "landsat_true": {
        "label_en": "Landsat — True colour",
        "label_pt": "Landsat — Cor natural",
        "note_en": "Annual cloud-free composite. Move the year slider below.",
        "note_pt": "Composto anual sem nuvens. Use o controle de ano abaixo.",
        "vis": {"bands": ["red", "green", "blue"], "min": 0.0, "max": 0.3,
                "gamma": 1.2},
    },
    "landsat_nir": {
        "label_en": "Landsat — False colour (NIR)",
        "label_pt": "Landsat — Falsa-cor (NIR)",
        "note_en": ("Near-infrared in the red channel: vegetation reads bright "
                    "red, which makes clearings and burns legible."),
        "note_pt": ("Infravermelho no canal vermelho: a vegetação aparece em "
                    "vermelho vivo, realçando cortes e queimadas."),
        "vis": {"bands": ["nir", "red", "green"], "min": 0.0, "max": 0.4,
                "gamma": 1.2},
    },
}

#: Every basemap the Canada panel offers, in display order. Unlike Brazil's
#: ``ALL_BASEMAPS`` there is no licence flag to gate on — the Landsat composites
#: are public, so nothing here can be dropped at import time.
ALL_BASEMAPS: Dict[str, Dict[str, Any]] = {
    **BASEMAPS,
    **LANDSAT_RENDERINGS,
}


def is_landsat_basemap(key: str) -> bool:
    return key in LANDSAT_RENDERINGS


#: Opening basemap. Google hybrid, same as Brazil: it carries place names and
#: roads, which is what tells a user where on a very large country they are.
DEFAULT_BASEMAP = "google_hybrid"
