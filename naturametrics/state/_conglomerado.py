"""Hovering and clicking an IFN conglomerado.

The conglomerados are drawn twice on purpose (see ``services.ifn.vector_spec``):
as Earth Engine tiles at every zoom, and — once the user is close enough for a
dot to be a target rather than a speck — as real geometry that can be hovered and
clicked. This mixin owns what those two gestures mean.

**Hover** is a preview, not an analysis. It reads two MapBiomas years over the
10 km buffer (~0.5 s, measured) and shows what is there now against what was
there in 1985. That is a deliberate limit: a full 40-year, 4-buffer analysis on
hover would be a promise the interface cannot keep while the cursor is moving.

**Click** is the analysis, at the conglomerado's own published coordinates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import reflex as rx

from ..services.mapbiomas_history import preview_land_cover

logger = logging.getLogger(__name__)

#: How many previews to remember. Sweeping back and forth across a screenful of
#: conglomerados must not re-query the ones already seen.
_PREVIEW_CACHE_MAX = 200


class ConglomeradoMixin(rx.State, mixin=True):
    """The conglomerado under the cursor."""

    hover_visible: bool = False
    hover_conglomerado: str = ""
    hover_place: str = ""
    hover_bioma: str = ""
    hover_loading: bool = False
    hover_error: str = ""
    hover_rows: list[dict[str, str]] = []
    hover_natural: str = ""
    hover_note: str = ""

    #: Only the newest hover may write to the card. Without this, moving from a
    #: slow point to a fast one shows the slow one's answer under the fast one's
    #: name — which is worse than showing nothing.
    _hover_token: int = 0
    _preview_cache: dict[str, Any] = {}

    @rx.event(background=True)
    async def preview_conglomerado(self, props: dict):
        """Fill the hover card for one conglomerado, or clear it.

        The hook sends ``{}`` when the cursor leaves, after a grace period.
        """
        if not props or not props.get("conglomerado"):
            async with self:
                self._hover_token += 1
                self.hover_visible = False
                self.hover_loading = False
                # Hand the preview back to the study point rather than blanking
                # the map: after clicking a conglomerado and moving the cursor
                # away, its buffer is still the thing being analysed.
                if self.has_point:
                    self._set_preview(self.study_lat, self.study_lon)
                else:
                    self._clear_preview()
            return

        key = str(props.get("ponto_id") or props.get("conglomerado"))
        place = " · ".join(
            str(x) for x in (props.get("municipio"), props.get("uf")) if x
        )

        try:
            hover_lat, hover_lon = float(props["lat"]), float(props["lon"])
        except (KeyError, TypeError, ValueError):
            hover_lat = hover_lon = None

        async with self:
            self._hover_token += 1
            token = self._hover_token
            if hover_lat is not None:
                # Before the Earth Engine call, not after: the clip is free and
                # showing it immediately is what makes the hover feel connected
                # to the map rather than to a spinner.
                self._set_preview(hover_lat, hover_lon)
            self.hover_visible = True
            self.hover_conglomerado = str(props.get("conglomerado", ""))
            self.hover_place = place
            self.hover_bioma = str(props.get("bioma", ""))
            self.hover_error = ""
            cached = self._preview_cache.get(key)
            if cached is not None:
                self._apply_preview(cached)
                return
            self.hover_loading = True
            self.hover_rows = []
            self.hover_natural = ""

        if hover_lat is None:
            async with self:
                if token == self._hover_token:
                    self.hover_loading = False
                    self.hover_error = "Coordenadas do conglomerado indisponíveis."
            return
        lat, lon = hover_lat, hover_lon

        # On a cold instance the prefetch may not have reached this year yet, and
        # the preview would silently draw nothing. Minting it here costs one call
        # and only ever happens once per year per process.
        if self.mapbiomas_year not in self._mb_urls:
            await self._ensure_year(self.mapbiomas_year)

        loop = asyncio.get_running_loop()
        try:
            from ..services.geo import point
            preview = await loop.run_in_executor(
                None, preview_land_cover, point(lat=lat, lon=lon))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Preview failed for %s: %s", key, exc)
            async with self:
                if token == self._hover_token:
                    self.hover_loading = False
                    self.hover_error = "Não foi possível ler a cobertura aqui."
            return

        async with self:
            if len(self._preview_cache) >= _PREVIEW_CACHE_MAX:
                self._preview_cache.clear()
            self._preview_cache[key] = preview
            if token != self._hover_token:
                return  # the cursor has already moved on; the cache still gains
            self._apply_preview(preview)

    def _apply_preview(self, preview: dict[str, Any]) -> None:
        """Render one preview into the card's display vars."""
        self.hover_loading = False
        if preview.get("empty"):
            self.hover_rows = []
            self.hover_natural = ""
            self.hover_note = "Sem cobertura mapeada neste raio."
            return
        self.hover_rows = [
            {"name": str(r["class_pt"]), "color": str(r["color"]),
             "pct": str(r["pct_label"]),
             # Signed and in percentage points, with the sign kept for zero-ish
             # values so the column reads as a change column, not a second share.
             "delta": ("+" if r["delta"] > 0 else "") +
                      f"{r['delta']:.1f}".replace(".", ",") + " pp"}
            for r in preview["rows"]
        ]
        first, last = preview["natural_first"], preview["natural_last"]
        self.hover_natural = (
            f"Vegetação natural {str(last).replace('.', ',')}% "
            f"(era {str(first).replace('.', ',')}% em {preview['first_year']})"
        )
        self.hover_note = (
            f"Composição em {preview['last_year']} num raio de "
            f"{preview['radius_km']:g} km. Clique para a análise completa."
        )

    def select_conglomerado(self, props: dict):
        """Make this conglomerado the study point and run the full analysis."""
        try:
            lat, lon = float(props["lat"]), float(props["lon"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Conglomerado click without usable coordinates: %s", props)
            return

        # Reuse the ordinary click path so validation, the buffer rings and the
        # analysis kick-off stay in one place; then stamp the identity it clears.
        event = self.set_study_point(lat, lon)
        if not self.has_point:
            return event

        self.point_source = "conglomerado IFN"
        self.point_conglomerado = str(props.get("conglomerado", ""))
        self.point_uf = str(props.get("uf", ""))
        self.point_municipio = str(props.get("municipio", ""))
        self.point_bioma = str(props.get("bioma", ""))
        self.hover_visible = False
        logger.info("Study point set from conglomerado %s", self.point_conglomerado)
        return event
