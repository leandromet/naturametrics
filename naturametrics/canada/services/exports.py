"""The Canada study-point workbook.

One spreadsheet for the point on screen, built entirely from numbers already
computed to draw the charts — nothing is recomputed, so the file and the screen
cannot disagree (the same contract as the Brazil export).

The ODS writer itself (:mod:`naturametrics.services.ods`) is shared unchanged;
only the choice of tabs is Canadian.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ...services import ods
from ..config import aafc

logger = logging.getLogger(__name__)

DATA_SOURCES = [
    ("AAFC Annual Crop Inventory",
     "Agriculture and Agri-Food Canada. Open Government Licence – Canada.",
     "https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI"),
    ("NTEMS Canada forest age (2019)",
     "Natural Resources Canada / National Forest Information System; "
     "Hermosilla et al. Canada Landsat-derived stand age.",
     "https://developers.google.com/earth-engine/datasets/catalog/"
     "CANADA_NFIS_NTEMS_CA_FOREST_AGE"),
    ("Hansen Global Forest Change v1.13",
     "Hansen, M. C. et al. (2013). High-Resolution Global Maps of "
     "21st-Century Forest Cover Change. Science 342, 850–853. CC-BY 4.0.",
     "https://glad.earthengine.app/view/global-forest-change"),
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
        ["page", "Naturametrics Canada"],
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
    rows = [
        [code, aafc.ACI_LABELS_EN[code], aafc.ACI_LABELS_PT.get(code, ""),
         aafc.color(code)]
        for code in sorted(aafc.ACI_LABELS_EN)
    ]
    return ods.Sheet("aafc_classes",
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
    age: list[dict[str, Any]],
    age_prov: dict[str, Any] | None,
    point_age: dict[str, Any] | None,
    change: dict[str, Any],
    change_prov: dict[str, Any] | None,
    loss_series: list[dict[str, Any]],
) -> tuple[bytes, str]:
    """Build the workbook. Returns ``(bytes, filename)``."""
    sheets: list[ods.Sheet] = [
        _metadata_sheet(
            [
                ("crop inventory history", history_prov),
                ("pixel series", pixel_prov),
                ("forest age", age_prov),
                ("forest change", change_prov),
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
                f"aci_{radius:g}km", sub,
                ["year", "class_id", "class_en", "class_pt", "pixels", "area_ha"]))
    else:
        sheets.append(ods.Sheet(
            "aci_empty", ["note"],
            [["No AAFC Annual Crop Inventory coverage at this location — see "
              "the metadata tab and the app's help panel on coverage limits."]]))

    px_df = pd.DataFrame(pixel)
    if not px_df.empty:
        sheets.append(ods.sheet_from_dataframe(
            "pixel_by_year", px_df, ["year", "class_id", "class_en", "class_pt"]))

    age_df = pd.DataFrame(age)
    if not age_df.empty:
        sheets.append(ods.sheet_from_dataframe(
            "forest_age", age_df, ["radius_km", "bin", "area_ha"]))

    if point_age:
        sheets.append(ods.Sheet(
            "forest_age_point", ["field", "value"],
            [["reference_year", point_age.get("reference_year")],
             ["is_forest", point_age.get("is_forest")],
             ["age_years", point_age.get("age")],
             ["age_bin", point_age.get("bin")]]))

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

    sheets.append(_class_dictionary_sheet())

    data = ods.write(sheets)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    name = f"naturametrics_canada_{lat:.4f}_{lon:.4f}_{stamp}.ods"
    logger.info("Canada workbook built: %s sheets, %s bytes", len(sheets), len(data))
    return data, name
