"""Provenance records.

Constraint **C6** (doc/01-premises.md): any number the app shows must be traceable
to the dataset, bands, geometry, scale and reducer that produced it. This is
enforced structurally — analysis functions return ``(data, Provenance)`` and the
export handlers refuse to write a file without one — rather than by convention,
because provenance added later is provenance nobody trusts.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any


@dataclasses.dataclass
class Provenance:
    """How one analysis result was produced."""

    name: str
    dataset_id: str
    bands: list[str] = dataclasses.field(default_factory=list)
    scale_m: int = 30
    reducer: str = ""
    pixel_area_basis: str = ""
    max_pixels: float = 1e10
    tile_scale: int = 4
    geometry: dict[str, Any] | None = None
    #: True when the retry ladder had to coarsen scale or raise tileScale. A
    #: degraded result is usable and exportable, but it must say so (doc/11 §3).
    degraded: bool = False
    notes: list[str] = dataclasses.field(default_factory=list)
    computed_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)

    def degrade(self, note: str, *, scale_m: int | None = None,
                tile_scale: int | None = None) -> None:
        """Record a fallback. Never coarsen a query without calling this."""
        self.degraded = True
        if scale_m is not None:
            self.scale_m = scale_m
        if tile_scale is not None:
            self.tile_scale = tile_scale
        self.notes.append(note)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
