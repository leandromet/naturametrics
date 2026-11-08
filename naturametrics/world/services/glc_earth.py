"""Earth Engine parts of the /mundo page: GLC-FCS30D tile layers, the land-cover class at a point,
and Copernicus relief. Every call goes through the suite's shared client and tile cache."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ...services.ee_client import get_ee
from ...services.tiles import get_tile_url

DATA = Path(__file__).parent.parent / "data"
DEM = "COPERNICUS/DEM/GLO30_2024_1"
#: The four GLC tile groups the global view loads together (west, south, east, north).
GROUPS: dict[str, tuple[float, float, float, float]] = {
    "americas": (-180.0, -60.0, -30.0, 90.0),
    "europe_africa": (-30.0, -60.0, 60.0, 90.0),
    "central_asia": (60.0, -60.0, 110.0, 90.0),
    "australasia": (110.0, -60.0, 180.0, 90.0),
}
#: The groups loaded at the start (Brazil and Africa in view); the others on request.
START_GROUPS = ("americas", "europe_africa")
#: The three countries on the page: a box to show their GLC tiles, and a first view.
COUNTRIES: dict[str, dict[str, Any]] = {
    "br": {"box": (-74.5, -34.0, -34.0, 5.5), "view": (-13.0, -53.0, 3.6)},
    "ca": {"box": (-141.0, 41.0, -52.0, 84.0), "view": (56.0, -100.0, 2.8)},
    "us": {"box": (-125.0, 24.0, -66.0, 50.0), "view": (39.0, -98.0, 3.2)},
    "global": {"box": None, "view": (20.0, 10.0, 1.4)},
}
YEARS = tuple(range(2000, 2023))


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    return json.loads((DATA / "glc_tiles.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def legend() -> dict[str, Any]:
    return json.loads((DATA / "glc_legend.json").read_text(encoding="utf-8"))


def group_of(lon: float) -> str:
    """The tile group a longitude falls in (the groups tile the world by longitude)."""
    for name, (w, _s, e, _n) in GROUPS.items():
        if w <= lon < e:
            return name
    return "australasia" if lon >= 180 else "americas"


def band_for_year(year: int) -> str:
    return f"b{year - 1999}"


def tile_bounds(name: str) -> tuple[int, int, int, int]:
    """West, south, east, north of a tile from its name. The latitude number is the north edge
    (checked against the assets' footprints in Earth Engine)."""
    body = name[len(_index()["prefix"]):-len(_index()["suffix"])]
    m = re.fullmatch(r"([EW])(\d+)([NS])(\d+)", body)
    if m is None:
        raise ValueError(f"not a GLC-FCS30D tile name: {name}")
    west = int(m.group(2)) * (1 if m.group(1) == "E" else -1)
    north = int(m.group(4)) * (1 if m.group(3) == "N" else -1)
    return west, north - 5, west + 5, north


def tile_name(west: int, north: int) -> str:
    lon = f"{'E' if west >= 0 else 'W'}{abs(west)}"
    lat = f"{'N' if north >= 0 else 'S'}{abs(north)}"
    return f"{_index()['prefix']}{lon}{lat}{_index()['suffix']}"


def tiles_in_box(box: tuple[float, float, float, float]) -> list[str]:
    w, s, e, n = box
    out = []
    for name in _index()["tiles"]:
        tw, ts, te, tn = tile_bounds(name)
        if tw < e and te > w and ts < n and tn > s:
            out.append(name)
    return out


def tile_covering(lat: float, lon: float) -> str | None:
    """The tile holding a point, or None (ocean, or no tile)."""
    west = math.floor(lon / 5) * 5
    north = math.floor(lat / 5) * 5 + 5
    name = tile_name(west, north)
    return name if name in set(_index()["tiles"]) else None


def _mosaic(ee, year: int, box: tuple[float, float, float, float] | None):
    names = tiles_in_box(box) if box else list(_index()["tiles"])
    band = band_for_year(year)
    asset = _index()["asset_dir"]
    imgs = [ee.Image(f"{asset}/{n}").select(band) for n in names]
    return ee.ImageCollection.fromImages(imgs).mosaic()


def tile_url(key: str, year: int, box: tuple[float, float, float, float] | None) -> str | None:
    """A GLC-FCS30D tile URL for a year over a box (no box: every tile). No-data and sea water are
    transparent, so the basemap shows through; continental water is kept."""
    year = min(max(year, YEARS[0]), YEARS[-1])
    cache_key = f"nm_world_glc_sea_{key}_{year}"

    def build():
        ee = get_ee()
        img = _mosaic(ee, year, box)
        # Water is hidden only over the sea: the Copernicus DEM has no data over the ocean, so
        # inland water (lakes, rivers) stays where the DEM has values.
        coll = ee.ImageCollection(DEM).select("DEM")
        dem = coll.mosaic()
        keep = img.neq(0).And(img.neq(210).Or(dem.mask()))
        return img.updateMask(keep)

    return get_tile_url(cache_key, build, {"min": 0, "max": 255, "palette": legend()["palette"]})


def landcover(lat: float, lon: float, year: int) -> dict[str, Any] | None:
    """The GLC-FCS30D class at a point (its tile only; one Earth Engine request)."""
    name = tile_covering(lat, lon)
    if name is None:
        return None
    ee = get_ee()
    year = min(max(year, YEARS[0]), YEARS[-1])
    img = ee.Image(f"{_index()['asset_dir']}/{name}").select(band_for_year(year))
    got = img.reduceRegion(reducer=ee.Reducer.first(), geometry=ee.Geometry.Point([lon, lat]),
                           scale=30, maxPixels=1e6).getInfo() or {}
    value = got.get(band_for_year(year))
    if value is None:
        return None
    code = int(value)
    info = legend()["legend"].get(str(code), {})
    return {"year": year, "code": code, "pt": info.get("pt", str(code)), "en": info.get("en", str(code)),
            "group": info.get("group", ""), "color": info.get("hex", "#808080")}


def terrain(lat: float, lon: float, radius_km: float = 5.0) -> dict[str, Any] | None:
    """Elevation (m: min, mean, max) and mean slope (°) in a circle, from Copernicus GLO-30."""
    ee = get_ee()
    coll = ee.ImageCollection(DEM).select("DEM")
    dem = coll.mosaic().setDefaultProjection(coll.first().projection())
    slope = ee.Terrain.slope(dem)
    geom = ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000.0, maxError=1)
    reducer = (ee.Reducer.min().combine(ee.Reducer.mean(), sharedInputs=True)
               .combine(ee.Reducer.max(), sharedInputs=True))
    stats = dem.rename("elev").addBands(slope.rename("slope")).reduceRegion(
        reducer=reducer, geometry=geom, scale=30, maxPixels=1e9, bestEffort=True).getInfo() or {}
    if stats.get("elev_min") is None:
        return None
    return {"radius_km": radius_km, "elev_min": stats["elev_min"], "elev_mean": stats["elev_mean"],
            "elev_max": stats["elev_max"], "slope": stats.get("slope_mean")}
