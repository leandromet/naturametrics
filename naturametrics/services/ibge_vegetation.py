"""IBGE Vegetação (2022, 1:250.000) buffer histories, and a QC comparison
against MapBiomas 2022.

**Vector, rasterized once, not a polygon-intersection.** The source asset
(``config.ibge_vegetation.IBGE_VEG_ASSET``) is a 145,458-feature
``FeatureCollection``, not an image. Intersecting that many polygons against
every buffer would be the vector equivalent of the mistake this app's tile
layer never makes: ``fc.reduceToImage([field], ee.Reducer.first())`` turns it
into a single-band classified image once, after which every buffer read is the
same ``reduceRegions(frequencyHistogram)`` + true ``pixelArea`` pattern this
app already uses for MapBiomas (``services.mapbiomas_history``) and biomass
(``services.biomass``) — never a nominal ha/pixel constant.

**The comparison is a joint histogram, not two side-by-side ones.** IBGE's
``leg2_id`` (1-54) and MapBiomas' class code share no numeric range, so they
are combined into one band via ``ibge.multiply(1000).add(mapbiomas)`` — the
same encode-two-classes-as-one-int trick used for classification-transition
analysis — and read with a single ``frequencyHistogram``. Splitting the
combined key back into ``(leg2_id, mb_class)`` in Python costs nothing extra
and is exact: this is one Earth Engine round trip for what a class-by-class
comparison would otherwise need as an intersection.

**Both datasets get reduced to the same six buckets**
(``config.ibge_vegetation``: natural/anthropic × forest/non-forest, plus water
and other) before the comparison is shown — the two legends don't share
classes, so a raw 54×~30 matrix would answer nothing a person could read. The
raw ``leg2_id``/``mb_class`` pairs stay in the returned long-form frame and in
``Provenance.extra`` for anyone who wants to drill down; only the bucketed
matrix is what the panel displays.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..config import ibge_vegetation as iv
from ..config import mapbiomas as mb
from ..config.settings import (
    BUFFER_RADII_KM, EE_MAX_PIXELS, EE_TILE_SCALE, EE_DEFAULT_SCALE_M,
)
from .buffers import (
    BufferMode, BufferShape, buffer_collection,
    full_area_bbox, full_area_collection, full_area_geojson,
)
from .ee_client import get_ee
from .geo import Point, validate_for_analysis
from .provenance import Provenance

logger = logging.getLogger(__name__)

VEG_COLUMNS = [
    "radius_km", "leg2_id", "label_pt", "group", "color",
    "pixels", "area_ha", "area_pct",
]
COMPARISON_COLUMNS = [
    "radius_km", "leg2_id", "ibge_group", "mb_class", "mb_group",
    "pixels", "area_ha", "area_pct",
]


def _classified_image():
    """The IBGE vegetation FeatureCollection rasterized to one band, ``leg2``.

    Built fresh (not disk-cached) on every call: the Earth Engine graph is
    lazy, so this costs nothing until something actually reduces it — unlike
    ``services.biomes``' vector path, this image never leaves Earth Engine as
    geometry, so there is no browser payload to precompute.
    """
    import ee
    return (
        ee.FeatureCollection(iv.IBGE_VEG_ASSET)
        .reduceToImage([iv.IBGE_VEG_CLASS_FIELD], ee.Reducer.first())
        .rename("leg2")
    )


def _histogram_call(fc, image, scale: int, tile_scale: int):
    import ee
    return (
        image.reduceRegions(
            collection=fc, reducer=ee.Reducer.frequencyHistogram(),
            scale=scale, tileScale=tile_scale,
        ).getInfo()
    )


def _pixel_area_call(fc, scale: int, tile_scale: int):
    import ee
    return (
        ee.Image.pixelArea()
        .reduceRegions(collection=fc, reducer=ee.Reducer.mean(),
                       scale=scale, tileScale=tile_scale)
        .getInfo()
    )


def _mean_px_area(areas: dict) -> dict[float, float]:
    return {
        f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
        for f in areas["features"]
    }


def _retry_ladder(fc, image, *, label: str, prov: Provenance):
    """Same three-step retry ladder as ``mapbiomas_history``/``biomass`` — a
    single-band histogram and a pixelArea mean, issued together so the pair
    costs one round-trip of wall-clock, not two."""
    from concurrent.futures import ThreadPoolExecutor

    scale, tile_scale = EE_DEFAULT_SCALE_M, EE_TILE_SCALE
    hist = areas = None
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (60, 8)]):
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_hist = ex.submit(_histogram_call, fc, image, s, ts)
                f_area = ex.submit(_pixel_area_call, fc, s, ts)
                hist, areas = f_hist.result(), f_area.result()
            if attempt > 0:
                prov.degrade(
                    f"Retried at scale={s} m, tileScale={ts} after a failure at "
                    f"scale={scale} m, tileScale={tile_scale}.",
                    scale_m=s, tile_scale=ts,
                )
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s attempt %s (scale=%s, tileScale=%s) failed: %s",
                           label, attempt + 1, s, ts, exc)
            if attempt == 2:
                raise
    return hist, areas


# --------------------------------------------------------------------------- #
# IBGE-only history
# --------------------------------------------------------------------------- #

def _veg_from_collection(
    fc: Any, *, geometry: dict[str, Any] | None, point_label: str,
    mode: str, shape: str, radii_km: tuple[float, ...],
) -> tuple[pd.DataFrame, Provenance]:
    image = _classified_image()
    prov = Provenance(
        name="ibge_vegetation_history",
        dataset_id=iv.IBGE_VEG_ASSET,
        bands=["leg2"],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=geometry,
        extra={"buffer_mode": mode, "buffer_shape": shape,
               "radii_km": list(radii_km), "point": point_label,
               "attribution": iv.IBGE_VEG_ATTRIBUTION},
    )

    hist, areas = _retry_ladder(fc, image, label="ibge_vegetation", prov=prov)
    px_area = _mean_px_area(areas)

    records: list[dict[str, Any]] = []
    for feat in hist["features"]:
        props = feat["properties"]
        radius = float(props["radius_km"])
        area_per_px_ha = px_area.get(radius, 900.0) / 10_000.0
        histogram = props.get("histogram") or {}
        for class_id, count in histogram.items():
            count = float(count)
            if count <= 0:
                continue
            leg2_id = int(float(class_id))
            records.append({
                "radius_km": radius,
                "leg2_id": leg2_id,
                "label_pt": iv.IBGE_VEG_LABELS_PT.get(leg2_id, f"Classe {leg2_id}"),
                "group": iv.ibge_group(leg2_id),
                "color": iv.IBGE_VEG_COLOR_MAP.get(leg2_id, "999999"),
                "pixels": count,
                "area_ha": count * area_per_px_ha,
            })

    df = pd.DataFrame.from_records(records, columns=VEG_COLUMNS[:-1])
    if not df.empty:
        totals = df.groupby("radius_km")["area_ha"].transform("sum")
        df["area_pct"] = (df["area_ha"] / totals * 100.0).fillna(0.0)
        df = df.sort_values(["radius_km", "area_ha"], ascending=[True, False]).reset_index(drop=True)

    prov.extra["mean_pixel_area_m2"] = {str(k): round(v, 2) for k, v in px_area.items()}
    prov.extra["n_records"] = len(df)
    return df, prov


def veg_history(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
) -> tuple[pd.DataFrame, Provenance]:
    """IBGE vegetation class area by buffer — a single 2022 snapshot, no year axis."""
    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode, shape)
    return _veg_from_collection(
        fc, geometry=p.to_geojson(), point_label=str(p),
        mode=mode, shape=shape, radii_km=radii_km,
    )


def full_area_veg_history(
    points: list[Point],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
) -> tuple[pd.DataFrame, Provenance]:
    get_ee()
    bbox = full_area_bbox(points, radii_km, shape)
    fc = full_area_collection(points, radii_km, shape, bbox=bbox)
    df, prov = _veg_from_collection(
        fc, geometry=full_area_geojson(points, radii_km, shape, bbox=bbox),
        point_label=f"{len(points)} points (full area)",
        mode="full_area", shape=shape, radii_km=radii_km,
    )
    prov.extra["n_points"] = len(points)
    prov.extra["outer_radius_km"] = max(radii_km)
    prov.extra["bbox_wgs84"] = list(bbox)
    return df, prov


def aggregate_veg_history(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several conglomerados' IBGE histories — same overlap-counted-once-
    per-conglomerado reading as ``mapbiomas_history.aggregate_histories``."""
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=VEG_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    out = (
        combined.groupby(["radius_km", "leg2_id"], as_index=False)[["pixels", "area_ha"]].sum()
    )
    out["label_pt"] = out["leg2_id"].map(lambda c: iv.IBGE_VEG_LABELS_PT.get(int(c), f"Classe {int(c)}"))
    out["group"] = out["leg2_id"].map(lambda c: iv.ibge_group(int(c)))
    out["color"] = out["leg2_id"].map(lambda c: iv.IBGE_VEG_COLOR_MAP.get(int(c), "999999"))
    totals = out.groupby("radius_km")["area_ha"].transform("sum")
    out["area_pct"] = (out["area_ha"] / totals * 100.0).fillna(0.0)
    return out.sort_values(["radius_km", "area_ha"], ascending=[True, False]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# MapBiomas comparison
# --------------------------------------------------------------------------- #

def _comparison_from_collection(
    fc: Any, *, mb_year: int, geometry: dict[str, Any] | None, point_label: str,
    mode: str, shape: str, radii_km: tuple[float, ...],
) -> tuple[pd.DataFrame, Provenance]:
    import ee

    asset = mb.MAPBIOMAS_COLLECTIONS[mb.MAPBIOMAS_DEFAULT_COLLECTION]
    mb_image = ee.Image(asset).select(mb.band_for_year(mb_year)).rename("mb")
    ibge_image = _classified_image()
    # Encode both classes into one int band: exact and splits back with plain
    # arithmetic — no risk of collision since leg2_id is 1-54 and MapBiomas
    # class codes never reach 1000.
    combined = ibge_image.multiply(1000).add(mb_image).rename("combined").toInt()

    prov = Provenance(
        name="ibge_mapbiomas_comparison",
        dataset_id=f"{iv.IBGE_VEG_ASSET} × {asset}",
        bands=["leg2", f"mapbiomas_{mb_year}"],
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram (combined leg2*1000 + mapbiomas class)",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=geometry,
        extra={"buffer_mode": mode, "buffer_shape": shape,
               "radii_km": list(radii_km), "point": point_label,
               "mapbiomas_year": mb_year,
               "attribution": iv.IBGE_VEG_ATTRIBUTION,
               "caveat": (
                   "Both datasets are simplified to a shared 6-bucket "
                   "natural/anthropic × forest taxonomy for this comparison "
                   "(config.ibge_vegetation) — it is not the source "
                   "classification of either dataset. 'anthropic_regrowth' "
                   "(IBGE Vegetação Secundária) has no MapBiomas equivalent by "
                   "design; the matrix shows what MapBiomas currently reads "
                   "those polygons as instead."
               )},
    )

    hist, areas = _retry_ladder(fc, combined, label="ibge_mapbiomas_comparison", prov=prov)
    px_area = _mean_px_area(areas)

    records: list[dict[str, Any]] = []
    for feat in hist["features"]:
        props = feat["properties"]
        radius = float(props["radius_km"])
        area_per_px_ha = px_area.get(radius, 900.0) / 10_000.0
        histogram = props.get("histogram") or {}
        for key, count in histogram.items():
            count = float(count)
            if count <= 0:
                continue
            combined_id = int(float(key))
            leg2_id, mb_class = divmod(combined_id, 1000)
            records.append({
                "radius_km": radius,
                "leg2_id": leg2_id,
                "ibge_group": iv.ibge_group(leg2_id),
                "mb_class": mb_class,
                "mb_group": iv.mapbiomas_group(mb_class),
                "pixels": count,
                "area_ha": count * area_per_px_ha,
            })

    df = pd.DataFrame.from_records(records, columns=COMPARISON_COLUMNS[:-1])
    if not df.empty:
        totals = df.groupby("radius_km")["area_ha"].transform("sum")
        df["area_pct"] = (df["area_ha"] / totals * 100.0).fillna(0.0)
        df = df.sort_values(["radius_km", "area_ha"], ascending=[True, False]).reset_index(drop=True)

    prov.extra["mean_pixel_area_m2"] = {str(k): round(v, 2) for k, v in px_area.items()}
    prov.extra["n_records"] = len(df)
    return df, prov


def mapbiomas_comparison(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
    mb_year: int = iv.IBGE_COMPARE_YEAR,
) -> tuple[pd.DataFrame, Provenance]:
    """Joint IBGE-vegetation × MapBiomas area histogram, one buffer at a time."""
    get_ee()
    validate_for_analysis(p)
    fc = buffer_collection(p, radii_km, mode, shape)
    return _comparison_from_collection(
        fc, mb_year=mb_year, geometry=p.to_geojson(), point_label=str(p),
        mode=mode, shape=shape, radii_km=radii_km,
    )


def full_area_mapbiomas_comparison(
    points: list[Point],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
    mb_year: int = iv.IBGE_COMPARE_YEAR,
) -> tuple[pd.DataFrame, Provenance]:
    get_ee()
    bbox = full_area_bbox(points, radii_km, shape)
    fc = full_area_collection(points, radii_km, shape, bbox=bbox)
    df, prov = _comparison_from_collection(
        fc, mb_year=mb_year, geometry=full_area_geojson(points, radii_km, shape, bbox=bbox),
        point_label=f"{len(points)} points (full area)",
        mode="full_area", shape=shape, radii_km=radii_km,
    )
    prov.extra["n_points"] = len(points)
    prov.extra["outer_radius_km"] = max(radii_km)
    prov.extra["bbox_wgs84"] = list(bbox)
    return df, prov


def aggregate_veg_comparison(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several conglomerados' joint histograms — same reasoning as
    ``aggregate_veg_history``/``mapbiomas_history.aggregate_histories``."""
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=COMPARISON_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    out = (
        combined.groupby(["radius_km", "leg2_id", "mb_class"], as_index=False)[["pixels", "area_ha"]].sum()
    )
    out["ibge_group"] = out["leg2_id"].map(lambda c: iv.ibge_group(int(c)))
    out["mb_group"] = out["mb_class"].map(lambda c: iv.mapbiomas_group(int(c)))
    totals = out.groupby("radius_km")["area_ha"].transform("sum")
    out["area_pct"] = (out["area_ha"] / totals * 100.0).fillna(0.0)
    return out.sort_values(["radius_km", "area_ha"], ascending=[True, False]).reset_index(drop=True)


def bucket_matrix(df: pd.DataFrame, radius_km: float) -> dict[str, Any]:
    """Pivot one buffer's joint histogram to a 6x6 (ibge_group x mb_group) %
    matrix, plus the two headline numbers the panel leads with: how much of
    the buffer each dataset calls forest, and how much each calls natural.

    Returns a plain dict (not a DataFrame) since this is exactly what the
    Reflex component needs to render — a dict of dicts round-trips through
    state cleanly, a DataFrame does not.
    """
    empty = {
        "groups": iv.GROUP_ORDER, "matrix": {}, "forest_ibge": 0.0,
        "forest_mb": 0.0, "natural_ibge": 0.0, "natural_mb": 0.0,
    }
    if df is None or df.empty or "radius_km" not in df.columns:
        return empty
    sub = df[df["radius_km"] == radius_km]
    if sub.empty:
        return empty

    # Cast up front, not just on the numerator: dividing a Python float by a
    # bare pandas/numpy scalar upcasts the result right back to numpy.float64,
    # which Reflex's state serialization does not accept.
    total = float(sub["area_ha"].sum())
    matrix: dict[str, dict[str, float]] = {
        g: {g2: 0.0 for g2 in iv.GROUP_ORDER} for g in iv.GROUP_ORDER
    }
    for _, row in sub.iterrows():
        pct = float(row["area_ha"]) / total * 100.0 if total else 0.0
        matrix[row["ibge_group"]][row["mb_group"]] += pct

    forest_groups = {iv.GROUP_NATURAL_FOREST, iv.GROUP_ANTHROPIC_FOREST}
    natural_groups = {iv.GROUP_NATURAL_FOREST, iv.GROUP_NATURAL_NON_FOREST}

    def marginal(axis: str, groups: set[str]) -> float:
        col = sub.groupby(axis)["area_ha"].sum()
        return float(col[col.index.isin(groups)].sum() / total * 100.0) if total else 0.0

    return {
        "groups": iv.GROUP_ORDER,
        "matrix": matrix,
        "forest_ibge": round(marginal("ibge_group", forest_groups), 1),
        "forest_mb": round(marginal("mb_group", forest_groups), 1),
        "natural_ibge": round(marginal("ibge_group", natural_groups), 1),
        "natural_mb": round(marginal("mb_group", natural_groups), 1),
    }
