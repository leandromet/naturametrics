"""MapBiomas land-cover history for a set of buffers.

This is the performance-critical path (doc/06-ee-layers.md §4). MapBiomas
Collection 10.1 ships all 40 years as 40 **bands of one image**, so the whole
"40 years × 4 buffers" matrix is a *single* ``reduceRegions`` — not because we
are rationing Earth Engine calls (the Partner tier makes that irrelevant) but
because one round-trip beats 160 sequential ones.

**Area accounting (decision D3).** Pixel counts alone would need a flat
0.09 ha/pixel assumption, which drifts with latitude. Instead a second, concurrent
call measures the *mean true pixel area* inside each buffer with
``ee.Image.pixelArea()``, and areas are ``count × mean_pixel_area``. Within a
single buffer the pixel area varies by far less than the classification error, so
this is exact for practical purposes and costs one extra cheap round-trip issued
in parallel. ``tests/test_area_accounting.py`` checks it against a per-class
grouped reducer, which is the textbook-exact method.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

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


def _histogram_call(fc, asset: str, bands: list[str], scale: int, tile_scale: int):
    import ee
    return (
        ee.Image(asset)
        .select(bands)
        .reduceRegions(
            collection=fc,
            reducer=ee.Reducer.frequencyHistogram(),
            scale=scale,
            tileScale=tile_scale,
        )
        .getInfo()
    )


def _pixel_area_call(fc, scale: int, tile_scale: int):
    """Mean true pixel area (m²) inside each buffer — the D3 area basis."""
    import ee
    return (
        ee.Image.pixelArea()
        .reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=scale,
            tileScale=tile_scale,
        )
        .getInfo()
    )


def land_cover_history(
    p: Point,
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    mode: BufferMode = "disc",
    shape: BufferShape = "circle",
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Land-cover area by year, class and buffer.

    Returns a long-format frame — ``radius_km, year, class_id, pixels, area_ha`` —
    plus the provenance record that must travel with it (constraint C6).

    Long format rather than wide-by-year: 40 years × ~15 classes × 4 buffers is a
    natural long table, and wide-by-year breaks the moment the year range changes.
    """
    # First statement, before validation, and idempotent: see the note in
    # ee_client.get_ee. A browser tab that was open across a backend restart
    # never re-runs the app's on_mount initialiser, so any path that assumes
    # someone else initialised Earth Engine fails for every call until the page
    # is reloaded — which looks like the data is broken, not the session.
    get_ee()
    validate_for_analysis(p)

    years = years or mb.MAPBIOMAS_YEARS
    bands = [mb.band_for_year(y) for y in years]
    asset = mb.MAPBIOMAS_COLLECTIONS[collection]
    fc = buffer_collection(p, radii_km, mode, shape)

    return _history_from_collection(
        fc, asset=asset, bands=bands, years=years, geometry=p.to_geojson(),
        point_label=str(p), collection=collection, mode=mode, shape=shape,
        radii_km=radii_km,
    )


def full_area_land_cover_history(
    points: list[Point],
    radii_km: tuple[float, ...] = BUFFER_RADII_KM,
    shape: BufferShape = "circle",
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """Land-cover history over the single bounding box enclosing every
    selected point's *outer* buffer, instead of summing per-point buffers
    (``aggregate_histories``).

    No overlap to double-count — the trade is that the box also covers
    whatever land sits between clusters, which is not part of any individual
    buffer. One box at the largest radius, not one per radius — a smaller
    radius's box would nest entirely inside it. See
    ``services.buffers.full_area_bbox`` for how the box itself is built, and
    doc/01-premises.md for how this differs from the sum.
    """
    get_ee()

    years = years or mb.MAPBIOMAS_YEARS
    bands = [mb.band_for_year(y) for y in years]
    asset = mb.MAPBIOMAS_COLLECTIONS[collection]
    bbox = full_area_bbox(points, radii_km, shape)
    fc = full_area_collection(points, radii_km, shape, bbox=bbox)

    df, prov = _history_from_collection(
        fc, asset=asset, bands=bands, years=years,
        geometry=full_area_geojson(points, radii_km, shape, bbox=bbox),
        point_label=f"{len(points)} points (full area)", collection=collection,
        mode="full_area", shape=shape, radii_km=radii_km,
    )
    prov.extra["n_points"] = len(points)
    prov.extra["outer_radius_km"] = max(radii_km)
    prov.extra["bbox_wgs84"] = list(bbox)
    return df, prov


def _history_from_collection(
    fc: Any,
    *,
    asset: str,
    bands: list[str],
    years: list[int],
    geometry: dict[str, Any] | None,
    point_label: str,
    collection: str,
    mode: str,
    shape: str,
    radii_km: tuple[float, ...],
) -> tuple[pd.DataFrame, Provenance]:
    """Shared reduceRegions/retry/parsing body behind :func:`land_cover_history`
    and :func:`full_area_land_cover_history` — everything downstream of "here is
    one ``ee.FeatureCollection`` with a ``radius_km`` property per feature" is
    generic over where that collection's geometry came from.
    """
    from concurrent.futures import ThreadPoolExecutor

    prov = Provenance(
        name="landuse_history",
        dataset_id=asset,
        bands=bands,
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="frequencyHistogram",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=geometry,
        extra={"collection": collection, "buffer_mode": mode, "buffer_shape": shape,
               "radii_km": list(radii_km), "point": point_label},
    )

    scale, tile_scale = EE_DEFAULT_SCALE_M, EE_TILE_SCALE
    hist = areas = None

    # Retry ladder (doc/06 §4). Never coarsen without recording it.
    for attempt, (s, ts) in enumerate([(scale, tile_scale), (scale, 8), (60, 8)]):
        try:
            # Both calls are independent, so issue them together: the pair costs
            # one round-trip of wall-clock, not two.
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_hist = ex.submit(_histogram_call, fc, asset, bands, s, ts)
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
            logger.warning("history attempt %s (scale=%s, tileScale=%s) failed: %s",
                           attempt + 1, s, ts, exc)
            if attempt == 2:
                raise

    px_area = {
        f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
        for f in areas["features"]
    }

    records: list[dict[str, Any]] = []
    for feat in hist["features"]:
        props = feat["properties"]
        radius = props["radius_km"]
        area_per_px_ha = px_area.get(radius, 900.0) / 10_000.0

        # Earth Engine names the reduceRegions output per BAND when several
        # bands are selected, but falls back to the reducer's own name
        # ("histogram") when there is exactly one. A parser that only looks for
        # "classification_*" therefore returns nothing at all for a single-year
        # query — silently, as an empty frame rather than an error.
        single_band = len(bands) == 1
        for key, histogram in props.items():
            if not isinstance(histogram, dict):
                continue
            if key.startswith("classification_"):
                year = int(key.rsplit("_", 1)[1])
            elif single_band and key == "histogram":
                year = years[0]
            else:
                continue
            for class_id, count in histogram.items():
                count = float(count)
                if count <= 0:
                    continue
                records.append({
                    "radius_km": float(radius),
                    "year": year,
                    "class_id": int(float(class_id)),
                    "pixels": count,
                    "area_ha": count * area_per_px_ha,
                })

    df = pd.DataFrame.from_records(
        records, columns=["radius_km", "year", "class_id", "pixels", "area_ha"]
    )
    if not df.empty:
        df["class_pt"] = df["class_id"].map(lambda c: mb.label(c, "pt"))
        df["class_en"] = df["class_id"].map(lambda c: mb.label(c, "en"))
        df["color"] = df["class_id"].map(mb.color)
        df = df.sort_values(["radius_km", "year", "area_ha"],
                            ascending=[True, True, False]).reset_index(drop=True)

    prov.extra["mean_pixel_area_m2"] = {str(k): round(v, 2) for k, v in px_area.items()}
    prov.extra["n_records"] = len(df)
    logger.info("History for %s: %s records across %s buffers", point_label, len(df), len(px_area))
    return df, prov


def to_shares(df: pd.DataFrame, radius_km: float) -> pd.DataFrame:
    """Per-year percentage shares for one buffer — what the stacked chart plots."""
    if df is None or df.empty or "radius_km" not in df.columns:
        return pd.DataFrame()
    sub = df[df["radius_km"] == radius_km].copy()
    if sub.empty:
        return sub
    totals = sub.groupby("year")["area_ha"].transform("sum")
    sub["area_pct"] = (sub["area_ha"] / totals * 100.0).fillna(0.0)
    return sub


def point_pixel_series(
    p: Point,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    years: list[int] | None = None,
) -> tuple[pd.DataFrame, Provenance]:
    """The MapBiomas class at the point's own 30 m pixel, one row per year.

    This is a different measurement from the buffer histograms, not a summary of
    them: it is what the classifier says about *this* pixel, with no averaging
    to hide behind. A single 30 m pixel is noisy — one misclassified year shows
    up as a spurious transition — and every export that carries this table also
    carries that warning (doc/11 §2).

    One ``reduceRegion`` over all 40 bands, ~0.3 s.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    years = years or mb.MAPBIOMAS_YEARS
    bands = [mb.band_for_year(y) for y in years]
    asset = mb.MAPBIOMAS_COLLECTIONS[collection]

    prov = Provenance(
        name="point_pixel_series",
        dataset_id=asset,
        bands=bands,
        scale_m=EE_DEFAULT_SCALE_M,
        reducer="first",
        pixel_area_basis="n/a — single pixel, no area computed",
        max_pixels=EE_MAX_PIXELS,
        tile_scale=EE_TILE_SCALE,
        geometry=p.to_geojson(),
        extra={"collection": collection, "point": str(p)},
    )

    values = (
        ee.Image(asset)
        .select(bands)
        .reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=p.to_ee_point(),
            scale=EE_DEFAULT_SCALE_M,
            tileScale=EE_TILE_SCALE,
            maxPixels=EE_MAX_PIXELS,
        )
        .getInfo()
    ) or {}

    records = []
    for year in years:
        raw = values.get(mb.band_for_year(year))
        class_id = int(raw) if raw is not None else None
        records.append({
            "year": year,
            "class_id": class_id,
            # A pixel outside the mapped area returns None. Labelling it "sem
            # dado" rather than dropping the row keeps the series continuous,
            # which is what makes a gap visible instead of invisible.
            "class_pt": mb.label(class_id, "pt") if class_id is not None else "Sem dado",
            "class_en": mb.label(class_id, "en") if class_id is not None else "No data",
        })

    df = pd.DataFrame.from_records(records)
    prov.extra["n_years"] = len(df)
    prov.extra["n_missing"] = int(df["class_id"].isna().sum())
    return df, prov


def preview_land_cover(
    p: Point,
    radius_km: float = 10.0,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
) -> dict[str, Any]:
    """A quick land-cover sketch of one buffer, for the hover card.

    Deliberately *not* the full analysis. It reads two bands — the first and last
    years — over a single buffer, which measured 0.25–0.7 s and is what makes
    showing it on hover honest rather than a promise the interface cannot keep.
    Clicking the conglomerado runs the real thing.

    Two years rather than one because the composition alone says what is there
    now, and the question a user is actually asking while sweeping across a grid
    of sampling points is what *changed*.
    """
    import ee

    get_ee()
    validate_for_analysis(p)

    first_year, last_year = mb.MAPBIOMAS_YEAR_START, mb.MAPBIOMAS_YEAR_END
    bands = [mb.band_for_year(first_year), mb.band_for_year(last_year)]
    asset = mb.MAPBIOMAS_COLLECTIONS[collection]

    raw = (
        ee.Image(asset)
        .select(bands)
        .reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=p.to_ee_point().buffer(radius_km * 1000.0),
            scale=EE_DEFAULT_SCALE_M,
            tileScale=EE_TILE_SCALE,
            maxPixels=EE_MAX_PIXELS,
        )
        .getInfo()
    ) or {}

    def shares(band: str) -> dict[int, float]:
        hist = raw.get(band) or {}
        counts = {int(float(k)): float(v) for k, v in hist.items() if float(v) > 0}
        total = sum(counts.values())
        if not total:
            return {}
        return {k: v / total * 100.0 for k, v in counts.items()}

    first, last = shares(bands[0]), shares(bands[1])
    if not last:
        return {"radius_km": radius_km, "rows": [], "empty": True}

    rows = [
        {
            "class_id": class_id,
            "class_pt": mb.label(class_id, "pt"),
            "class_en": mb.label(class_id, "en"),
            "color": mb.color(class_id),
            "pct": round(pct, 1),
            "pct_label": f"{pct:.1f}%".replace(".", ","),
            # Percentage *points* of change, not a ratio: "+12 pp" is the
            # comparison a share invites, and a ratio off a 0.1 % base is noise
            # dressed up as a finding.
            "delta": round(pct - first.get(class_id, 0.0), 1),
        }
        for class_id, pct in sorted(last.items(), key=lambda kv: -kv[1])[:6]
    ]

    def natural(shares_map: dict[int, float]) -> float:
        return sum(v for k, v in shares_map.items() if k in mb.NATURAL_VEGETATION)

    return {
        "radius_km": radius_km,
        "first_year": first_year,
        "last_year": last_year,
        "rows": rows,
        "natural_first": round(natural(first), 1),
        "natural_last": round(natural(last), 1),
        "empty": False,
    }


def aggregate_histories(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum several conglomerados' buffer histories into one.

    Areas and pixel counts are **added** per (radius, year, class) — the natural
    reading of "these fifty places together". Percentages are deliberately *not*
    carried over from the inputs and are recomputed from the summed areas, since
    an average of percentages over buffers is not the percentage of the whole.

    The buffers of two conglomerados 12 km apart overlap, and the overlap is
    counted twice. That is the honest meaning of a sum over sampling units — each
    unit contributes its own landscape — but it means the total is *not* the area
    of the union, and the chart says so.
    """
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["radius_km", "year", "class_id", "pixels",
                                     "area_ha", "class_pt", "class_en", "color"])

    combined = pd.concat(frames, ignore_index=True)
    out = (
        combined.groupby(["radius_km", "year", "class_id"], as_index=False)
        [["pixels", "area_ha"]].sum()
    )
    out["class_pt"] = out["class_id"].map(lambda c: mb.label(int(c), "pt"))
    out["class_en"] = out["class_id"].map(lambda c: mb.label(int(c), "en"))
    out["color"] = out["class_id"].map(lambda c: mb.color(int(c)))
    return out.sort_values(["radius_km", "year", "area_ha"],
                           ascending=[True, True, False]).reset_index(drop=True)
