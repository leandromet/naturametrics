"""Earth Engine asset identifiers and their visualisation parameters.

Every entry is documented in doc/04-data-sources.md with its licence and caveats.
Verified against the Earth Engine catalogue on 2026-08-18.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from .settings import SPOT_ENABLED

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

#: Earth-Engine-backed basemaps. Unlike everything above, these are not XYZ
#: URLs: a tile URL has to be minted per session, so they are switched on by a
#: background event rather than a plain state write (see state/_layers.py).
#:
#: The Brazil Forest 2008 mosaic is a **partial** layer — circa-2008 SPOT imagery
#: over Brazil's forest areas, not a global basemap. Gaps outside its footprint
#: are the dataset, not a failure, and the panel says so.
EE_BASEMAPS: Dict[str, Dict[str, Any]] = {
    "spot_2008_visual": {
        "label_pt": "SPOT 2008 — Visual (Brasil)",
        "label_en": "SPOT 2008 — Visual (Brazil)",
        "asset": "GOOGLE/BRAZIL_FOREST_2008/V1/VISUAL",
        "vis": {"bands": ["R", "G", "B"], "min": 0, "max": 255},
        "attribution": (
            "Google LLC, Brazil Forest Imagery Dataset 2008 created from circa "
            "2008 SPOT images"
        ),
        "max_native_zoom": 16,
        "note_pt": "Mosaico SPOT ~2008, só sobre áreas florestais do Brasil.",
        "note_en": "SPOT mosaic, ~2008, covering only Brazil's forest areas.",
    },
    "spot_2008_analytic": {
        "label_pt": "SPOT 2008 — Falsa-cor (NIR)",
        "label_en": "SPOT 2008 — False colour (NIR)",
        "asset": "GOOGLE/BRAZIL_FOREST_2008/V1/ANALYTIC",
        # N,R,G puts near-infrared in the red channel: vegetation reads bright
        # red, which is what makes 2008 forest cover legible against pasture.
        "vis": {"bands": ["N", "R", "G"], "min": [156, 62, 53],
                "max": [6408, 2584, 2211], "gamma": 0.9},
        "attribution": (
            "Google LLC, Brazil Forest Imagery Dataset 2008 created from circa "
            "2008 SPOT images"
        ),
        "max_native_zoom": 16,
        "note_pt": "Infravermelho em vermelho: vegetação de 2008 aparece realçada.",
        "note_en": "Near-infrared shown in red: 2008 vegetation appears highlighted.",
    },
}

#: Every basemap the panel offers, XYZ and Earth Engine alike, in display order.
#: The SPOT entries are dropped entirely when the licence flag is off, rather
#: than offered and then failing: an option that never works is worse than an
#: option that is not there.
ALL_BASEMAPS: Dict[str, Dict[str, Any]] = {
    **BASEMAPS,
    **(EE_BASEMAPS if SPOT_ENABLED else {}),
}


def is_ee_basemap(key: str) -> bool:
    return key in EE_BASEMAPS


#: Overridable with NM_BASEMAP. Hybrid rather than plain imagery: the study
#: points are identified by município and UF, and a satellite basemap with no
#: labels makes checking that you are where you think you are impossible.
DEFAULT_BASEMAP = os.environ.get("NM_BASEMAP", "google_hybrid")

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
#: Global Forest Change — also the map layer under "Mudança florestal
#: (Hansen)" (services/layers.py::hansen_treecover_spec/hansen_change_spec),
#: ported from the Canada page's canada/services/layers.py so both pages
#: agree on what "forest" means for this dataset.
HANSEN_GFC = {
    "asset": "UMD/hansen/global_forest_change_2025_v1_13",
    "loss_year_start": 2001,
    "loss_year_end": 2024,  # lossyear band: 1..24 → 2001..2024
    "treecover_vis": {"min": 0, "max": 100,
                      "palette": ["ffffff", "d9f0a3", "78c679", "238443", "004529"]},
    "loss_color": "#d4271e",
    "gain_color": "#02d659",
    "attribution": "Hansen/UMD/Google/USGS/NASA — Global Forest Change",
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


# --------------------------------------------------------------------------- #
# Own Earth Engine assets (project ee-leandromet)
# --------------------------------------------------------------------------- #
# Uploaded 2026-08-19 from the shapefiles in
# ~/Documents/2026_inma_gustavo/shapes_google. These are the only assets the
# application reads from its OWN project — everything else is public. If the
# app ever runs under a different GCP project (settings.GCP_PROJECT_ID) these
# two must be shared with it, or both layers fail while the rest still work.

#: SFB IFN conglomerado locations, exactly as uploaded — 17 495 points.
#:
#: ⚠️ **The map does not read this one; it reads IFN_POINTS_JOINED below.** This
#: is the raw upload and the input to scripts/join_ifn_biomes.py. It is kept
#: named here so the join has a source and so the provenance of the joined asset
#: is one lookup away, not so that layers point at it.
#:
#: ``data/ifn_points.csv`` (scripts/fetch_ifn.py) stays as the *attribute*
#: source, since it carries the survey date, ``impedimento`` and the derived
#: status that neither asset has. The two are joined on the UA identifier when a
#: point is selected.
#:
#: ⚠️ Defects, verified against the asset (doc/04-data-sources.md §6a.1):
#: 16 features have an EMPTY MultiPoint geometry and cannot be drawn, joined or
#: filtered; 24 carry empty ``sigla_uf``/``nm_mun``/``nm_regiao``. Usable: 17 479.
IFN_POINTS = {
    "asset": "projects/ee-leandromet/assets/sfb_ifn_conglomerados_pontos",
    "count": 17495,
    "attribution": (
        "Serviço Florestal Brasileiro — Inventário Florestal Nacional "
        "(conglomerados)"
    ),
    #: Semantic name → property name in the asset. Nothing outside this dict
    #: should hard-code the abbreviated shapefile column names.
    "fields": {
        "region": "nm_regiao",
        "uf": "sigla_uf",
        "municipality": "nm_mun",
        "municipality_code": "cd_mun",
        "conglomerate": "no_conglom",
        "point_id": "co_pontos_",
    },
    #: ``FeatureCollection.style`` arguments. ``pointSize`` is in screen pixels,
    #: so the dots stay legible at every zoom instead of vanishing at z5.
    "style": {
        "color": "ffffff",
        "fillColor": "e5484dcc",
        "pointSize": 3,
        "pointShape": "circle",
        "width": 1,
    },
}

#: The IFN points with the biome joined in, written by
#: ``scripts/join_ifn_biomes.py --export-asset``. **This is what the map reads.**
#:
#: The join has to be materialised rather than done at query time: filtering the
#: raw points with ``filterBounds`` against a biome outline works for Pantanal,
#: Pampa and Caatinga and fails for Amazônia, Cerrado and Mata Atlântica with
#: "Description length exceeds maximum" — those three outlines are too long for
#: Earth Engine's filter machinery at 1:250 000. Here ``bioma`` is a plain string
#: property, so all four filters are the same ``ee.Filter.eq`` and the request
#: size no longer depends on the size of the biome.
#:
#: The 16 features with empty geometry are dropped during the export, so this
#: asset holds 17 479 points to the source asset's 17 495.
IFN_POINTS_JOINED = {
    "asset": "projects/ee-leandromet/assets/sfb_ifn_conglomerados_pontos_bioma",
    "count": 17479,
    "attribution": (
        "Serviço Florestal Brasileiro — Inventário Florestal Nacional "
        "(conglomerados) · bioma: IBGE 1:250.000"
    ),
    "fields": {
        "region": "nm_regiao",
        "uf": "sigla_uf",
        "municipality": "nm_mun",
        "municipality_code": "cd_mun",
        "conglomerate": "no_conglom",
        "point_id": "co_pontos_",
        "biome": "bioma",
        "phyto_domain": "dominio_fito",
        "natural_region": "regiao_natural",
    },
    "style": {
        "color": "ffffff",
        "fillColor": "e5484dcc",
        "pointSize": 3,
        "pointShape": "circle",
        "width": 1,
    },
}

#: IBGE biomes, domains and natural regions, 1:250 000 — 271 polygons.
#: Used for the biome overlay and as the spatial filter behind the IFN "bioma"
#: selector (the point asset has no biome attribute of its own).
IBGE_BIOME_DOMAIN = {
    "asset": "projects/ee-leandromet/assets/ibge_biome_domain_250k",
    "attribution": "IBGE — Biomas e domínios morfoclimáticos 1:250.000",
    "fields": {
        "biome": "nm_bm",
        "biome_code": "cd_bm",
        "geology": "gl_dom",
        "geomorphology": "gm_dom",
        "vegetation": "vg_dom",
        "soil": "pd_dom",
        "phyto_domain": "nm_dm_fito",
        "natural_region": "nm_reg_nat",
    },
    #: The seven values actually present in ``nm_bm``, verified against the
    #: asset. Order is the legend order; it is also the filter dropdown order.
    "biomes": [
        "Amazônia",
        "Cerrado",
        "Mata Atlântica",
        "Caatinga",
        "Pampa",
        "Pantanal",
        "Ilhas Oceânicas",
    ],
    #: Roughly IBGE's own biome cartography. 8-digit hex: the last byte is alpha,
    #: kept low so the land cover underneath stays readable through the fill.
    "palette": {
        "Amazônia": "1a7f37",
        "Cerrado": "d9a441",
        "Mata Atlântica": "2f6f4e",
        "Caatinga": "c96a3a",
        "Pampa": "8fbf5a",
        "Pantanal": "3f8fbf",
        "Ilhas Oceânicas": "8a6fbf",
    },
    "fill_alpha": "59",   # ~35 % — a wash, not a mask
    "outline_alpha": "ff",
    "outline_width": 1.5,
}

# --------------------------------------------------------------------------- #
# IBAMA — SISCOM embargos (live ArcGIS FeatureServer, not Earth Engine)
# --------------------------------------------------------------------------- #
#: Areas embargoed by IBAMA for environmental infractions. Unlike everything
#: else in this file, this is not an Earth Engine asset: it is IBAMA's own
#: live service — see services/embargos.py, which queries it per-viewport
#: and never caches beyond a couple of minutes.
#:
#: ⚠️ This used to point at "01_Publicacoes_Bases/embargos_siscom_brasil"
#: (MapServer/2), which verified live 2026-08-31 as reachable but returning
#: **zero features nationwide** (returnCountOnly → {"count":0},
#: returnIdsOnly → objectIds: null) — presumably a feed between refresh
#: cycles rather than a dead endpoint, but unusable as-is. Re-pointed
#: 2026-08-31 at "01_Publicacoes_Bases/adm_embargos_ibama_a" instead — the
#: same publisher, a different underlying dataset (a WMS/WFS-capable
#: service the same MapServer also exposes; this app uses its plain REST
#: /query endpoint, the same mechanism as before, since REST bbox queries
#: already proved reliable and WFS's BBOX filter did not return matches
#: against a known point during verification) — confirmed live with real
#: data: 91 120 polygons nationwide (WFS resultType=hits), a REST bbox
#: query over a small Santa Catarina box returned 6 real embargoed
#: properties. Field names below were re-mapped to this dataset's own
#: (different) schema.
IBAMA_EMBARGOS = {
    "query_url": (
        "https://pamgia.ibama.gov.br/server/rest/services/"
        "01_Publicacoes_Bases/adm_embargos_ibama_a/MapServer/0/query"
    ),
    "attribution": "IBAMA — áreas embargadas",
    #: Semantic name → ArcGIS field name. Nothing outside services/embargos.py
    #: should hard-code the source field abbreviations.
    "fields": {
        "person": "nome_embargado",
        "document": "cpf_cnpj_embargado",
        "tad_number": "num_tad",
        "tad_date": "dat_embargo",
        "process": "num_processo",
        "uf": "uf",
        "municipality": "municipio",
        #: This dataset has no embargo-status field (the old source's
        #: sit_embarg/status_tad have no equivalent here) — sit_desmatamento
        #: is the closest available flag, but it answers a narrower question
        #: ("is deforestation ongoing on this property?", not "what state is
        #: the embargo in?"), so the tooltip labels it "Desmatamento", not
        #: "Situação", to avoid implying it says more than it does.
        "situation": "sit_desmatamento",
        "infraction": "des_tad",
        "area": "qtd_area_embargada",
        "agency": "unid_controle",
        "registered": "dat_ult_alteracao",
    },
    #: Amber — reads as a legal/regulatory flag, distinct from every other
    #: layer's palette on this map.
    "default_color": "f9a825",
}

# --------------------------------------------------------------------------- #
# IBAMA autos de infração (infraction notices) — live ArcGIS MapServer
# --------------------------------------------------------------------------- #
#: Individual infraction citations, as points — a different, complementary
#: dataset to IBAMA_EMBARGOS above (an "auto de infração" is the citation
#: itself; an embargo is the follow-on restriction placed on the land, and
#: not every citation carries one). Same publisher, same REST /query
#: mechanism, verified live 2026-08-31: 709 803 rows nationwide — far denser
#: than embargos, hence services/auto_infracao.py's own higher min_zoom.
#:
#: ⚠️ This service also exposes a WFS endpoint
#: (app_dadosabertos/adm_auto_infracao_p/MapServer/WFSServer), but its
#: outputFormat=geojson response is malformed for any record with no
#: recorded coordinate — literally invalid JSON (a dangling
#: ``"geometry":{"type":"Point",}`` with no ``coordinates`` key at all).
#: The plain REST /query endpoint used here does not have this problem
#: (confirmed against the same bbox), so WFS was dropped rather than worked
#: around.
IBAMA_AUTO_INFRACAO = {
    "query_url": (
        "https://pamgia.ibama.gov.br/server/rest/services/"
        "app_dadosabertos/adm_auto_infracao_p/MapServer/0/query"
    ),
    "attribution": "IBAMA — autos de infração",
    #: Semantic name → ArcGIS field name. Nothing outside
    #: services/auto_infracao.py should hard-code the source field names.
    "fields": {
        "infrator": "nome_infrator",
        "document": "cpf_cnpj_infrator",
        "auto_number": "num_auto_infracao",
        "date": "dat_hora_auto_infracao",
        "process": "num_processo",
        "uf": "uf",
        "municipality": "municipio",
        "infraction": "des_infracao",
        "value": "val_auto_infracao",
        "status": "des_status_formulario",
    },
    #: A deep orange-red — related to embargos' amber (both IBAMA
    #: enforcement data) but visually distinct from it, and from IFN's own
    #: red conglomerado dots.
    "default_color": "c1440e",
}

# --------------------------------------------------------------------------- #
# IBGE municípios — shared with camposcope (same ee-leandromet project)
# --------------------------------------------------------------------------- #
#: The same asset camposcope's own IBGE_MUNICIPIOS reads
#: (camposcope/config/datasets.py). Both apps run under the ee-leandromet GCP
#: project, so this is a read-only reference to an asset this app does not
#: own — see services/municipios.py. Used only to frame the map on a chosen
#: município (fitBounds); the searchable name list is a local CSV.
IBGE_MUNICIPIOS = {
    "asset": os.environ.get(
        "NM_MUNICIPIOS_ASSET",
        "projects/ee-leandromet/assets/br_municipios_2025",
    ),
    "attribution": "IBGE — Malhas territoriais municipais 2025",
    "fields": {"code": "CD_MUN"},
}
