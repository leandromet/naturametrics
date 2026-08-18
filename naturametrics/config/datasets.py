"""Earth Engine asset identifiers and their visualisation parameters.

Every entry is documented in doc/04-data-sources.md with its licence and caveats.
Verified against the Earth Engine catalogue on 2026-08-18.
"""

from __future__ import annotations

import os
from typing import Any, Dict

# --------------------------------------------------------------------------- #
# Basemaps (plain XYZ, no Earth Engine involved)
# --------------------------------------------------------------------------- #
# ⚠️ The `mt1.google.com` endpoints are not a licensed public Google API — they are
# the same undocumented tile servers Yvynation uses. They are fast and they work,
# and they are the chosen default; but before a public deployment this should
# become a proper Google Maps Platform key, or fall back to Esri/OSM, which are
# licensed for this use. Tracked in doc/04-data-sources.md §7.
BASEMAPS: Dict[str, Dict[str, Any]] = {
    "google_maps": {
        "label_pt": "Google Maps",
        "label_en": "Google Maps",
        "url": "https://mt1.google.com/vt/lyrs=r&x={x}&y={y}&z={z}",
        "attribution": "© Google",
        "max_native_zoom": 20,
    },
    "google_satellite": {
        "label_pt": "Google — Satélite",
        "label_en": "Google — Satellite",
        "url": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        "attribution": "© Google",
        "max_native_zoom": 20,
    },
    "google_hybrid": {
        "label_pt": "Google — Híbrido",
        "label_en": "Google — Hybrid",
        "url": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "attribution": "© Google",
        "max_native_zoom": 20,
    },
    "google_terrain": {
        "label_pt": "Google — Relevo",
        "label_en": "Google — Terrain",
        "url": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        "attribution": "© Google",
        "max_native_zoom": 20,
    },
    "esri_imagery": {
        "label_pt": "Esri — Satélite",
        "label_en": "Esri — Imagery",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles © Esri",
        "max_native_zoom": 19,
    },
    "esri_topo": {
        "label_pt": "Esri — Topográfico",
        "label_en": "Esri — Topographic",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles © Esri",
        "max_native_zoom": 19,
    },
    "osm": {
        "label_pt": "OpenStreetMap",
        "label_en": "OpenStreetMap",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "© OpenStreetMap contributors",
        "max_native_zoom": 19,
    },
}

#: Overridable with NM_BASEMAP.
DEFAULT_BASEMAP = os.environ.get("NM_BASEMAP", "esri_imagery")

# --------------------------------------------------------------------------- #
# MapBiomas auxiliary products
# --------------------------------------------------------------------------- #
#: Deforestation & Secondary Vegetation — the authoritative basis for regrowth
#: dating (doc/10 §3, estimator E1). Bands start at 1987, NOT 1985.
MAPBIOMAS_DSV = {
    "asset": (
        "projects/mapbiomas-public/assets/brazil/lulc/collection10_1/"
        "mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3"
    ),
    "year_start": 1987,
    "year_end": 2024,
    "band_template": "classification_{year}",
    "vis": {
        "min": 0,
        "max": 7,
        "palette": [
            "808080",  # 0 Outro
            "FFB266",  # 1 Antrópico
            "228B22",  # 2 Vegetação primária
            "90EE90",  # 3 Vegetação secundária
            "FF0000",  # 4 Desmatamento em primária   (evento)
            "00FF00",  # 5 Regeneração                (evento)
            "FF4500",  # 6 Desmatamento em secundária (evento)
            "A9A9A9",  # 7 Não aplicado
        ],
    },
}

#: Class codes. 2 and 3 are *stable states*; 4, 5 and 6 are *annual events*.
#: Conflating the two produces nonsense — see doc/04 §2b.
DSV_ANTHROPIC = 1
DSV_PRIMARY = 2
DSV_SECONDARY = 3
DSV_DEFOR_PRIMARY = 4
DSV_REGROWTH = 5
DSV_DEFOR_SECONDARY = 6

#: MapBiomas Fire Collection 4 — a qualifier on vegetation age, never an input (D7).
MAPBIOMAS_FIRE = {
    "frequency": {
        "asset": (
            "projects/mapbiomas-public/assets/brazil/fire/collection4/"
            "mapbiomas_fire_collection4_fire_frequency_v1"
        ),
        "band_candidates": ("fire_frequency_1985_2024", "fire_frequency"),
        "vis": {"min": 0, "max": 20,
                "palette": ["ffffff", "ffffb2", "fecc5c", "fd8d3c", "f03b20", "bd0026"]},
    },
    "year_last": {
        "asset": (
            "projects/mapbiomas-public/assets/brazil/fire/collection4/"
            "mapbiomas_fire_collection4_year_last_fire_v1"
        ),
        "band_candidates": ("classification_{year}", "year_last_fire", "last_fire_year"),
        "vis": {"min": 1985, "max": 2024,
                "palette": ["440154", "3b528b", "21918c", "5ec962", "fde725"]},
    },
}

# --------------------------------------------------------------------------- #
# Hansen
# --------------------------------------------------------------------------- #
#: Global Forest Change. Used ONLY as an independent stand-replacement
#: disturbance dater — never as a definition of forest (doc/10 §5.2).
HANSEN_GFC = {
    "asset": "UMD/hansen/global_forest_change_2025_v1_13",
    "loss_year_offset": 2000,  # lossyear 1..24 → 2001..2024
    "vis_treecover": {"bands": ["treecover2000"], "min": 0, "max": 100,
                      "palette": ["black", "green"]},
    "vis_lossyear": {"bands": ["lossyear"], "min": 0, "max": 24,
                     "palette": ["yellow", "red"]},
    "vis_gain": {"bands": ["gain"], "min": 0, "max": 1, "palette": ["#00FF00"]},
    "attribution": "Hansen/UMD/Google/USGS/NASA — Hansen et al. (2013) Science 342:850-853",
}

#: GLAD GLCLU2020 — 5-yearly strata. Map layer and coarse cross-check only;
#: too coarse in time to date establishment, so not part of the age estimator.
GLAD_GLCLU = {
    "assets": {
        "2000": "projects/glad/GLCLU2020/v2/LCLUC_2000",
        "2005": "projects/glad/GLCLU2020/v2/LCLUC_2005",
        "2010": "projects/glad/GLCLU2020/v2/LCLUC_2010",
        "2015": "projects/glad/GLCLU2020/v2/LCLUC_2015",
        "2020": "projects/glad/GLCLU2020/v2/LCLUC_2020",
    },
    "ocean_mask": "projects/glad/OceanMask",
}

# --------------------------------------------------------------------------- #
# Satellite imagery
# --------------------------------------------------------------------------- #
SENTINEL2 = {
    "collection": "COPERNICUS/S2_SR_HARMONIZED",
    "cloud_score": "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED",
    "cloud_score_band": "cs",
    "cloud_score_threshold": 0.60,  # documented useful range 0.50–0.65
    "vis_true": {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000},
    "vis_false": {"bands": ["B8", "B4", "B3"], "min": 0, "max": 3000},
    "attribution": "Copernicus Sentinel-2 / ESA",
}

LANDSAT = {
    "collections": {
        "LC09": "LANDSAT/LC09/C02/T1_L2",
        "LC08": "LANDSAT/LC08/C02/T1_L2",
        "LE07": "LANDSAT/LE07/C02/T1_L2",
        "LT05": "LANDSAT/LT05/C02/T1_L2",
    },
    # Collection-2 L2 optical scaling: DN * 0.0000275 - 0.2
    "scale_mult": 0.0000275,
    "scale_add": -0.2,
    # Band aliases differ by mission — L8/L9 vs L5/L7.
    "bands_true": {
        "LC09": ["SR_B4", "SR_B3", "SR_B2"],
        "LC08": ["SR_B4", "SR_B3", "SR_B2"],
        "LE07": ["SR_B3", "SR_B2", "SR_B1"],
        "LT05": ["SR_B3", "SR_B2", "SR_B1"],
    },
    "vis": {"min": 0.0, "max": 0.3},
    "attribution": "USGS/NASA Landsat",
}

MODIS_VI = {
    "collection": "MODIS/061/MOD13Q1",
    "scale_factor": 0.0001,
    "scale_m": 250,
    "vis_evi": {
        "min": -0.2, "max": 1.0,
        "palette": [
            "ffffff", "ce7e45", "df923d", "f1b555", "fcd163", "99b718", "74a901",
            "66a000", "529400", "3e8601", "207401", "056201", "004c00", "023b01",
            "012e01", "011d01", "011301",
        ],
    },
    "attribution": "NASA LP DAAC — MOD13Q1.061",
}

#: ⚠️ Licence-gated. Requires accepting the "Brazil Forest Imagery Dataset 2008"
#: agreement, granted to the service account that runs the app. Gated behind
#: settings.SPOT_ENABLED — fail closed with an explanation (doc/04 §2).
SPOT_2008 = {
    "visual": {
        "asset": "GOOGLE/BRAZIL_FOREST_2008/V1/VISUAL",
        "vis": {"bands": ["R", "G", "B"], "min": 0, "max": 255},
        "resolution_m": 5,
    },
    "analytic": {
        "asset": "GOOGLE/BRAZIL_FOREST_2008/V1/ANALYTIC",
        "vis": {"bands": ["N", "R", "G"], "min": [156, 62, 53],
                "max": [6408, 2584, 2211], "gamma": 0.9},
        "resolution_m": 10,
    },
    "attribution": (
        "Google LLC, Brazil Forest Imagery Dataset 2008 created from circa 2008 "
        "SPOT images"
    ),
}
