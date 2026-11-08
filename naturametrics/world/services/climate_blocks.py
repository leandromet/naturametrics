"""World climate, fire weather and Köppen at a point, from the world blocks in the bucket.

The same files as muda-clima's world view (``gs://muda-clima-grids/v1/world/``): one 10° block per
file at 0.5° (climate, gust), 0.25° (fire weather) and 1/120° (Köppen, 1° tiles inside the block).
Read-only; the blocks are downloaded once into a local cache, then memory-mapped by numpy.
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("NM_GRIDS_BUCKET", "muda-clima-grids")
PREFIX = os.environ.get("NM_GRIDS_PREFIX", "v1/world/")
CACHE = Path(os.environ.get("NM_GRIDS_CACHE", Path(tempfile.gettempdir()) / "naturametrics-world"))
#: A folder of block files to read before the cache and the bucket (local testing with all the data:
#: NM_WORLD_LOCAL=/path/to/muda-clima/app/data/world). Unset in production.
LOCAL = Path(os.environ["NM_WORLD_LOCAL"]) if os.environ.get("NM_WORLD_LOCAL") else None
_URL = "https://storage.googleapis.com/storage/v1/b/{bucket}/o/{obj}?alt=media"
_lock = threading.Lock()

BLOCK = 10
SCENARIOS = ("ssp245", "ssp585")
#: Median-across-models indicators: key → (unit, "abs" | "pct" change), as in muda-clima.
INDICATORS: dict[str, tuple[str, str]] = {
    "tmean": ("°C", "abs"), "hot_days": ("d/yr", "abs"), "precip": ("mm/yr", "pct"),
    "dry_days": ("d/yr", "abs"), "heavy_days": ("d/yr", "abs"), "txx": ("°C", "abs"),
    "rx1day": ("mm", "abs"), "water_balance": ("mm/yr", "abs"),
}
FIRE = {"fwi": ("FWI", "abs"), "fwi_n30": ("d/yr", "abs"), "fwi_np95": ("d/yr", "abs")}


class WorldDataMissing(RuntimeError):
    """The block file is neither in the cache nor in the bucket."""


def world_block(lat: float, lon: float) -> tuple[int, int] | None:
    """(west, south) of the 10° block holding a point; None south of 60°S or at/above 80°N."""
    if not (-180.0 <= lon < 180.0) or not (-60 <= lat < 80.0):
        return None
    return (-180 + math.floor((lon + 180) / BLOCK) * 10, -60 + math.floor((lat + 60) / BLOCK) * 10)


def _download(name: str, dest: Path) -> None:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_only"])
    url = _URL.format(bucket=BUCKET, obj=urllib.parse.quote(PREFIX + name, safe=""))
    resp = AuthorizedSession(creds).get(url, timeout=120)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)


@lru_cache(maxsize=64)
def _load(name: str) -> dict[str, Any] | None:
    """One block file as a dict of arrays; None when the block has no file (no land there)."""
    if LOCAL is not None and (LOCAL / name).exists():
        path = LOCAL / name
    else:
        path = CACHE / name
    if not path.exists():
        with _lock:
            if not path.exists():
                try:
                    _download(name, path)
                except Exception as exc:  # noqa: BLE001 — no file is an answer, not a crash
                    logger.info("world block %s not available: %s", name, str(exc)[:120])
                    return None
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def _cell(grid: dict[str, Any], lat: float, lon: float, shape: tuple[int, int]) -> tuple[int, int] | None:
    step = float(grid["step"])
    row = math.floor((float(grid["north"]) - lat) / step)
    col = math.floor((lon - float(grid["west"])) / step)
    if row == shape[0]:                   # exactly on the south edge: the last row
        row = shape[0] - 1
    if col == shape[1]:
        col = shape[1] - 1
    return (row, col) if 0 <= row < shape[0] and 0 <= col < shape[1] else None


def _usable(v: float, missing: float) -> bool:
    return v == v and v > missing + 1.0


def climate_point(lat: float, lon: float) -> dict[str, Any] | None:
    """Per-model bands of the 0.5° climate cell, and the fire-weather bands when the block has them."""
    block = world_block(lat, lon)
    if block is None:
        return None
    grid = _load(f"nex_{block[0]}_{block[1]}.npz")
    if grid is None:
        return None
    rc = _cell(grid, lat, lon, grid["data"].shape[-2:])
    if rc is None:
        return None
    bands = [str(b) for b in grid["bands"]]
    missing = float(grid["missing"])
    models: dict[str, dict[str, float]] = {}
    for mi, model in enumerate(str(m) for m in grid["models"]):
        vals = grid["data"][mi, :, rc[0], rc[1]]
        if all(_usable(float(v), missing) for v in vals):
            row = {b: float(v) for b, v in zip(bands, vals, strict=True)}
            for part in ("base", *SCENARIOS):
                if f"{part}_precip" in row and f"{part}_pet" in row:
                    row[f"{part}_water_balance"] = row[f"{part}_precip"] - row[f"{part}_pet"]
            models[model] = row
    if not models:
        return None
    fire = _load(f"fwi_{block[0]}_{block[1]}.npz")
    if fire is not None:
        frc = _cell(fire, lat, lon, fire["data"].shape[-2:])
        if frc is not None:
            fbands = [str(b) for b in fire["bands"]]
            fmiss = float(fire["missing"])
            for mi, model in enumerate(str(m) for m in fire["models"]):
                if model in models:
                    vals = fire["data"][mi, :, frc[0], frc[1]]
                    if all(_usable(float(v), fmiss) for v in vals):
                        models[model].update({b: float(v) for b, v in zip(fbands, vals, strict=True)})
    return {"models": models, "step": float(grid["step"]), "hot_day_c": float(grid.get("hot_day_c", 35.0))}


def ensemble(models: dict[str, dict[str, float]], scenario: str) -> list[dict[str, Any]]:
    """Median baseline, future and change per indicator (climate and fire), across the models."""
    rows: list[dict[str, Any]] = []
    for key, (unit, kind) in {**INDICATORS, **FIRE}.items():
        pairs = [(m[f"base_{key}"], m[f"{scenario}_{key}"]) for m in models.values()
                 if f"base_{key}" in m and f"{scenario}_{key}" in m]
        if not pairs:
            continue
        base = float(np.median([b for b, _ in pairs]))
        fut = float(np.median([f for _, f in pairs]))
        change = (100.0 * (fut - base) / base if base else 0.0) if kind == "pct" else fut - base
        rows.append({"key": key, "unit": unit, "kind": kind, "baseline": base, "future": fut, "change": change})
    return rows


def koppen_point(lat: float, lon: float) -> dict[str, Any] | None:
    """Köppen-Geiger class at the point's 1 km pixel, today and under SSP2-4.5 and SSP5-8.5 mid-century."""
    from .koppen_labels import KOPPEN

    block = world_block(lat, lon)
    if block is None:
        return None
    z = _load(f"koppen_{block[0]}_{block[1]}.npz")
    if z is None:
        return None
    s, w = math.floor(lat), math.floor(lon)
    px = 120
    row = min(px - 1, int((s + 1 - lat) * px))
    col = min(px - 1, int((lon - w) * px))
    out: dict[str, Any] = {}
    for period in ("base", "ssp245", "ssp585"):
        key = f"{period}_{s}_{w}"
        if key in z:
            code = int(z[key][row, col])
            if code:
                out[period] = {"code": code, **KOPPEN[code]}
    return out or None


def point(lat: float, lon: float) -> dict[str, Any] | None:
    """Climate ensemble (SSP2-4.5 and SSP5-8.5), fire weather and Köppen at the point, or None."""
    got = climate_point(lat, lon)
    if got is None:
        return None
    return {"models": len(got["models"]), "step": got["step"], "hot_day_c": got["hot_day_c"],
            "ssp245": ensemble(got["models"], "ssp245"), "ssp585": ensemble(got["models"], "ssp585"),
            "koppen": koppen_point(lat, lon)}
