"""Landscape metrics and biomass for the USA page's results tabs (the Brazil page's own, on the
latest Annual NLCD year and the global biomass product).

Hawaii has no NLCD land cover, so the landscape tab says so there (the function returns ``None``).
Alaska uses its latest snapshot year (2016).
"""

from __future__ import annotations

from typing import Any

from ...services.biomass import biomass_history
from ...services.geo import Point
from ..config import nlcd
from ..services.geo import region_of, validate_for_analysis


def landscape_for_point(p: Point, radii_km: tuple[float, ...]):
    from ...services.landscape_metrics import landscape_metrics_on
    from .nlcd_history import nlcd_year_image
    validate_for_analysis(p)
    region = region_of(p) or "conus"
    if region in nlcd.NO_LANDCOVER:
        return None, None, None
    year = nlcd.years_for(region)[-1]
    image = nlcd_year_image(year, region).select(nlcd.NLCD_BAND).rename("class")
    dataset = nlcd.NLCD_DATASET if region == "conus" else nlcd.SNAPSHOT_COLLECTION
    band = nlcd.NLCD_BAND if region == "conus" else nlcd.SNAPSHOT_BAND
    summary, hist, prov = landscape_metrics_on(
        p, image, dataset_id=dataset, band_name=band, radii_km=radii_km)
    prov.extra.update({"year": year, "region": region})
    return summary, hist, prov


def biomass_for_point(p: Point, radii_km: tuple[float, ...]) -> tuple[Any, Any]:
    return biomass_history(p, radii_km, check_country=False)
