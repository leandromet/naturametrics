"""Natural-vegetation change between two years.

**Why 2008 is the default baseline.** Brazil's Forest Code (Lei 12.651/2012) uses
**22 July 2008** as its cut-off: native vegetation cleared *before* that date on
rural properties can be regularised as "área consolidada", while clearing *after*
it carries an obligation to restore. So "natural in 2008, not natural today" is
not an arbitrary difference — it is close to the legal definition of land with a
restoration obligation, and therefore the primary candidate set for recovery
projects.

It is also why the SPOT 2008 mosaic exists at all: Google built it for the
Brazilian Forest Code programme (its pre-publication asset path was literally
``projects/google/brazil_forest_code/…``). That gives 5 m imagery for the same
baseline year, so a candidate area can be checked by eye.

⚠️ **This is a screening tool, not a legal determination.** MapBiomas is annual
and 30 m; the Forest Code operates on a specific date, on cadastral parcels
(CAR), with exemptions for small holdings, APP/Reserva Legal distinctions, and
authorised clearing permits. Areas flagged here are *candidates to look at*, not
findings of illegality. The UI must say so wherever this layer is shown.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import mapbiomas as mb
from .ee_client import get_ee
from .provenance import Provenance
from .tiles import get_tile_url

logger = logging.getLogger(__name__)

#: Forest Code baseline year.
FOREST_CODE_BASELINE_YEAR = 2008

#: Output codes for the change mask.
CHANGE_LOSS = 1      # natural in baseline, not natural now  → restoration candidate
CHANGE_GAIN = 2      # not natural in baseline, natural now  → already recovering
CHANGE_STABLE = 3    # natural in both

CHANGE_LABELS_PT = {
    CHANGE_LOSS: "Perda veg. natural",
    CHANGE_GAIN: "Regeneração",
    CHANGE_STABLE: "Natural estável",
}
CHANGE_LABELS_EN = {
    CHANGE_LOSS: "Natural vegetation lost",
    CHANGE_GAIN: "Regrowth",
    CHANGE_STABLE: "Stable natural",
}
CHANGE_COLORS = {
    CHANGE_LOSS: "#e5484d",    # red — the restoration candidates
    CHANGE_GAIN: "#30a46c",    # green — recovery already happening
    CHANGE_STABLE: "#1f8d49",  # MapBiomas forest green
}


def _natural_mask(image, year: int):
    """1 where the pixel is natural vegetation in ``year``, else 0."""
    codes = sorted(mb.NATURAL_VEGETATION)
    band = image.select(mb.band_for_year(year))
    return band.remap(codes, [1] * len(codes), 0)


def change_mask_image(
    year_from: int = FOREST_CODE_BASELINE_YEAR,
    year_to: int = mb.MAPBIOMAS_YEAR_END,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    include_stable: bool = False,
):
    """Build the categorical change image.

    Returns an ``ee.Image`` with values :data:`CHANGE_LOSS`, :data:`CHANGE_GAIN`
    and optionally :data:`CHANGE_STABLE`; everything else is masked out so the
    layer overlays cleanly.
    """
    import ee

    img = ee.Image(mb.MAPBIOMAS_COLLECTIONS[collection])
    was = _natural_mask(img, year_from)
    now = _natural_mask(img, year_to)

    loss = was.eq(1).And(now.eq(0)).multiply(CHANGE_LOSS)
    gain = was.eq(0).And(now.eq(1)).multiply(CHANGE_GAIN)
    out = loss.add(gain)

    if include_stable:
        stable = was.eq(1).And(now.eq(1)).multiply(CHANGE_STABLE)
        out = out.add(stable)

    return out.selfMask().rename("change")


def change_mask_spec(
    year_from: int = FOREST_CODE_BASELINE_YEAR,
    year_to: int = mb.MAPBIOMAS_YEAR_END,
    opacity: float = 0.85,
    include_stable: bool = False,
    collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
    z_index: int = 20,
) -> dict[str, Any] | None:
    """Tile-layer spec for the change mask."""
    max_code = CHANGE_STABLE if include_stable else CHANGE_GAIN
    palette = [CHANGE_COLORS[c].lstrip("#")
               for c in range(1, max_code + 1)]
    vis = {"min": 1, "max": max_code, "palette": palette}

    key = (f"change:{collection}:{year_from}-{year_to}"
           f":{'stable' if include_stable else 'nostable'}")

    url = get_tile_url(
        key,
        lambda: change_mask_image(year_from, year_to, collection, include_stable),
        vis,
    )
    if url is None:
        return None

    return {
        "id": key,
        "url": url,
        "opacity": opacity,
        "attribution": f"MapBiomas {year_from}→{year_to} (mudança)",
        "z_index": z_index,
        "max_native_zoom": 15,
    }


def change_stats(p, radii_km, year_from: int = FOREST_CODE_BASELINE_YEAR,
                 year_to: int = mb.MAPBIOMAS_YEAR_END,
                 collection: str = mb.MAPBIOMAS_DEFAULT_COLLECTION,
                 mode: str = "disc") -> tuple[dict[float, dict[str, float]], Provenance]:
    """Area of loss / gain per buffer, in hectares.

    One ``reduceRegions`` for all buffers, using the same mean-pixel-area basis
    as the history query (decision D3). Returns ``(data, Provenance)`` like every
    other analysis entry point (constraint C6, doc/01-premises.md) — this one did
    not, until it needed to feed an exported sheet and C6 requires one for that.
    """
    import ee

    # First statement, before anything else — see the note in ee_client.get_ee
    # and the entry points in mapbiomas_history.py. This one had no equivalent
    # call anywhere in its path (change_mask_spec is covered transitively via
    # tiles.get_tile_url, but this function talks to Earth Engine directly).
    get_ee()

    from .buffers import buffer_collection
    from .geo import validate_for_analysis

    # Same guard every other analysis entry point has (mapbiomas_history,
    # vegetation_age): without it, a click outside Brazil silently reduces over
    # a geometry the MapBiomas-derived change mask has no data for and returns
    # an empty result that reads as a bug rather than an out-of-area click.
    validate_for_analysis(p)

    fc = buffer_collection(p, radii_km, mode)
    img = change_mask_image(year_from, year_to, collection, include_stable=True)
    asset = mb.MAPBIOMAS_COLLECTIONS[collection]

    prov = Provenance(
        name="change_stats",
        dataset_id=asset,
        bands=[mb.band_for_year(year_from), mb.band_for_year(year_to)],
        scale_m=30,
        reducer="frequencyHistogram + mean(pixelArea)",
        pixel_area_basis="mean ee.Image.pixelArea() per buffer (same basis as land-use history)",
        tile_scale=4,
        geometry=p.to_geojson(),
        extra={"year_from": year_from, "year_to": year_to, "buffer_mode": mode,
               "radii_km": list(radii_km), "point": str(p)},
    )

    hist = img.reduceRegions(
        collection=fc, reducer=ee.Reducer.frequencyHistogram(), scale=30, tileScale=4
    ).getInfo()
    areas = ee.Image.pixelArea().reduceRegions(
        collection=fc, reducer=ee.Reducer.mean(), scale=30, tileScale=4
    ).getInfo()

    px = {f["properties"]["radius_km"]: float(f["properties"].get("mean") or 900.0)
          for f in areas["features"]}

    out: dict[float, dict[str, float]] = {}
    for feat in hist["features"]:
        props = feat["properties"]
        radius = float(props["radius_km"])
        per_ha = px.get(radius, 900.0) / 10_000.0
        counts = {}
        for key, value in props.items():
            if isinstance(value, dict):
                counts = value
                break
        out[radius] = {
            "loss_ha": float(counts.get(str(CHANGE_LOSS), 0)) * per_ha,
            "gain_ha": float(counts.get(str(CHANGE_GAIN), 0)) * per_ha,
            "stable_ha": float(counts.get(str(CHANGE_STABLE), 0)) * per_ha,
        }
    prov.extra["n_buffers"] = len(out)
    return out, prov
