"""Landscape metrics and biomass for the Canada page's results tabs (the Brazil page's own,
on the Canadian classification and the global biomass product).

* :func:`landscape_for_point` — patches, edge, diversity on the latest AAFC crop inventory year.
  The inventory covers the settled south only; north of ~58°N the function returns an empty frame
  and a note, not an error.
* :func:`biomass_for_point` — the Brazil page's ``services.biomass.biomass_history`` (ESA CCI,
  global), reused as it is.
"""

from __future__ import annotations

from typing import Any

from ...services.biomass import biomass_history
from ...services.geo import Point
from ..config import aafc
from ..services.geo import validate_for_analysis


def aci_latest_image(year: int):
    import ee
    col = ee.ImageCollection(aafc.AACI_DATASET)
    img = ee.Image(col.filterDate(f"{year}-01-01", f"{year}-12-31").first())
    return img.select(aafc.ACI_BAND).rename("class")


def landscape_for_point(p: Point, radii_km: tuple[float, ...]):
    from ...services.landscape_metrics import landscape_metrics_on
    validate_for_analysis(p)
    if p.lat > aafc.ACI_NORTH_LIMIT_LAT:
        return None, None, None         # no inventory this far north: the tab says so
    year = aafc.ACI_YEAR_END
    summary, hist, prov = landscape_metrics_on(
        p, aci_latest_image(year), dataset_id=aafc.AACI_DATASET, band_name=aafc.ACI_BAND,
        radii_km=radii_km)
    prov.extra["year"] = year
    return summary, hist, prov


def biomass_for_point(p: Point, radii_km: tuple[float, ...]) -> tuple[Any, Any]:
    return biomass_history(p, radii_km, check_country=False)
