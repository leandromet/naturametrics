"""The USA study-point workbook.

One spreadsheet for the point on screen, built entirely from numbers already
computed to draw the charts — nothing is recomputed, so the file and the screen
cannot disagree (the same contract as the Brazil export).

The ODS writer itself (:mod:`naturametrics.services.ods`) is shared unchanged;
only the choice of tabs is American.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ...services import ods
from ..config import glc

logger = logging.getLogger(__name__)

DATA_SOURCES = [
    ("GLC-FCS30D annual land cover (2000–2022)",
     "Zhang, X. et al. (2021). GLC_FCS30D: the first global 30 m land-cover dynamics monitoring product "
     "with a fine classification system for 1985–2022 (the annual series used here starts in 2000). Earth System Science Data 13. CC BY 4.0. "
     "Redistributed in the Earth Engine community catalog "
     "(projects/sat-io/open-datasets/GLC-FCS30D/annual).",
     "https://doi.org/10.5281/zenodo.8239305"),
    ("Hansen Global Forest Change v1.13",
     "Hansen, M. C. et al. (2013). High-Resolution Global Maps of "
     "21st-Century Forest Cover Change. Science 342, 850–853. CC-BY 4.0. Tree-cover loss (2001–2025), "
     "tree cover in 2000, gain (2000–2012, undated).",
     "https://glad.earthengine.app/view/global-forest-change"),
    ("MODIS MCD64A1 burned area (v6.1)",
     "Giglio, L. et al. NASA LP DAAC. Monthly burned area at 500 m, from 2001. Public domain.",
     "https://lpdaac.usgs.gov/products/mcd64a1v061/"),
    ("Copernicus DEM GLO-30",
     "European Space Agency and the Copernicus programme. 30 m global elevation.",
     "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM"),
    ("NASA NEX-GDDP-CMIP6 and NEX-GDDP-FWI",
     "Thrasher, B. et al. (2022); Park, T. et al. NASA Earth Exchange downscaled climate and fire-weather "
     "projections, nine CMIP6 models. CC BY 4.0.",
     "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6"),
    ("Köppen-Geiger climate classes (1 km)",
     "Beck, H. E. et al. (2023). High-resolution (1 km) Köppen-Geiger maps for 1901–2099. "
     "Scientific Data 10, 724. CC BY 4.0.",
     "https://doi.org/10.1038/s41597-023-02549-6"),
    ("Landsat annual composites",
     "USGS/NASA Landsat Collection 2 Tier 1 Level-2 annual composites.",
     "https://developers.google.com/earth-engine/datasets/catalog/"
     "LANDSAT_COMPOSITES_C02_T1_L2_ANNUAL"),
    ("Google Earth Engine",
     "Gorelick, N. et al. (2017). Google Earth Engine: Planetary-scale "
     "geospatial analysis for everyone. Remote Sensing of Environment 202, 18–27.",
     "https://earthengine.google.com"),
]


def _metadata_sheet(entries: list[tuple[str, dict[str, Any] | None]],
                    point_label: str) -> ods.Sheet:
    """Provenance first, always — constraint C6.

    One row per (query, field) so the tab stays readable in a spreadsheet rather
    than being one cell of nested JSON.
    """
    rows: list[list[Any]] = [
        ["generated_utc", datetime.now(timezone.utc).isoformat(timespec="seconds")],
        ["page", "Naturametrics World"],
        ["study_point", point_label],
        ["", ""],
    ]
    for name, prov in entries:
        if not prov:
            rows.append([name, "not computed"])
            rows.append(["", ""])
            continue
        rows.append([f"— {name} —", ""])
        for key in ("dataset_id", "scale_m", "reducer", "pixel_area_basis",
                    "tile_scale", "max_pixels"):
            if prov.get(key) is not None:
                rows.append([key, prov.get(key)])
        bands = prov.get("bands") or []
        rows.append(["bands", ", ".join(map(str, bands)) if bands else ""])
        for key, value in (prov.get("extra") or {}).items():
            rows.append([f"extra.{key}", str(value)])
        if prov.get("degraded"):
            rows.append(["DEGRADED", "; ".join(prov.get("degradation_notes", []))])
        rows.append(["", ""])

    rows.append(["— attributions —", ""])
    for name, detail, url in DATA_SOURCES:
        rows.append([name, f"{detail} {url}"])

    return ods.Sheet("metadata", ["field", "value"], rows)


def _class_dictionary_sheet() -> ods.Sheet:
    legend = glc._legend()["legend"]
    rows = [
        [int(code), info["en"], info["pt"], info["hex"]]
        for code, info in sorted(legend.items(), key=lambda kv: int(kv[0]))
    ]
    return ods.Sheet("glc_classes",
                     ["class_id", "class_en", "class_pt", "colour_hex"], rows)


def study_point_workbook(
    *,
    point_label: str,
    lat: float,
    lon: float,
    history: list[dict[str, Any]],
    history_prov: dict[str, Any] | None,
    pixel: list[dict[str, Any]],
    pixel_prov: dict[str, Any] | None,
    change: dict[str, Any],
    change_prov: dict[str, Any] | None,
    loss_series: list[dict[str, Any]],
    dist: list[dict[str, Any]] | None = None,
    dist_prov: dict[str, Any] | None = None,
    age: list[dict[str, Any]] | None = None,
    age_prov: dict[str, Any] | None = None,
    fire: list[dict[str, Any]] | None = None,
    fire_prov: dict[str, Any] | None = None,
    canopy: list[dict[str, Any]] | None = None,
    canopy_prov: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    """Build the workbook. Returns ``(bytes, filename)``."""
    sheets: list[ods.Sheet] = [
        _metadata_sheet(
            [
                ("land cover history (GLC)", history_prov),
                ("pixel series", pixel_prov),
                ("forest change", change_prov),
                ("disturbance history (Hansen tree-cover loss)", dist_prov),
                ("time since disturbance (derived from Hansen loss)", age_prov),
                ("fire (MODIS burned area)", fire_prov),
                ("tree canopy cover", canopy_prov),
            ],
            point_label,
        )
    ]

    hist_df = pd.DataFrame(history)
    if not hist_df.empty:
        # One tab per radius, mirroring the Brazil workbook: it keeps each
        # radius under the per-sheet row limit on its own terms and is how a
        # reader actually wants to slice this.
        for radius in sorted(hist_df["radius_km"].unique()):
            sub = hist_df[hist_df["radius_km"] == radius]
            sheets.append(ods.sheet_from_dataframe(
                f"glc_{radius:g}km", sub,
                ["year", "class_id", "class_en", "class_pt", "pixels", "area_ha"]))

    px_df = pd.DataFrame(pixel)
    if not px_df.empty:
        sheets.append(ods.sheet_from_dataframe(
            "pixel_by_year", px_df, ["year", "class_id", "class_en", "class_pt"]))

    if change:
        # Column names carry their year ranges: loss spans 2001–2025 but gain
        # only 2000–2012, and a reader who nets the two bare columns would be
        # subtracting a 13-year figure from a 25-year one. The window column is
        # the one that nets honestly against gain.
        rows = [[r, v.get("loss_ha"), v.get("gain_ha"),
                 v.get("loss_gain_window_ha"),
                 round((v.get("gain_ha") or 0) - (v.get("loss_gain_window_ha") or 0), 2),
                 v.get("forest2000_ha")]
                for r, v in sorted(change.items(), key=lambda kv: float(kv[0]))]
        sheets.append(ods.Sheet(
            "forest_change",
            ["radius_km", "loss_2001_2025_ha", "gain_2000_2012_ha",
             "loss_2001_2012_ha", "net_2001_2012_ha", "forest2000_ha"], rows))

    loss_df = pd.DataFrame(loss_series)
    if not loss_df.empty:
        sheets.append(ods.sheet_from_dataframe(
            "loss_by_year", loss_df, ["year", "loss_ha"]))

    for name, rows, cols in (
        ("disturbance_by_year", dist, ["radius_km", "year", "class_id", "class_en", "class_pt", "area_ha"]),
        ("time_since_disturbance", age, ["radius_km", "bin", "area_ha"]),
        ("fire_modis_by_year", fire, ["radius_km", "year", "class_id", "class_en", "class_pt", "area_ha"]),
        ("tree_canopy_by_year", canopy, ["radius_km", "year", "canopy_pct"]),
    ):
        frame = pd.DataFrame(rows or [])
        if not frame.empty:
            sheets.append(ods.sheet_from_dataframe(name, frame, cols))

    sheets.append(_class_dictionary_sheet())

    data = ods.write(sheets)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    name = f"naturametrics_world_{lat:.4f}_{lon:.4f}_{stamp}.ods"
    logger.info("World workbook built: %s sheets, %s bytes", len(sheets), len(data))
    return data, name
