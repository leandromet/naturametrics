"""Landscape metrics and biomass for the world page's results tabs (the Brazil page's own, on the
latest GLC-FCS30D year and the global biomass product)."""

from __future__ import annotations

from typing import Any

from ...services.biomass import biomass_history
from ...services.ee_client import get_ee
from ...services.geo import Point
from ..config import glc
from ..services.geo import validate_for_analysis


def landscape_for_point(p: Point, radii_km: tuple[float, ...]):
    from ...services.landscape_metrics import landscape_metrics_on
    from .glc_history import buffer_box, glc_year_image
    get_ee()
    validate_for_analysis(p)
    year = glc.GLC_YEARS[-1]
    image = glc_year_image(year, buffer_box(p, max(radii_km))).select(glc.GLC_BAND).rename("class")
    summary, hist, prov = landscape_metrics_on(
        p, image, dataset_id=glc.GLC_DATASET, band_name=glc.GLC_BAND, radii_km=radii_km)
    prov.extra.update({"year": year, "region": "world"})
    return summary, hist, prov


def biomass_for_point(p: Point, radii_km: tuple[float, ...]) -> tuple[Any, Any]:
    return biomass_history(p, radii_km, check_country=False)
