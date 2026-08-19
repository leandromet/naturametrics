"""Hovering and clicking an IFN conglomerado.

The conglomerados are drawn twice on purpose (see ``services.ifn.vector_spec``):
as Earth Engine tiles at every zoom, and — once the user is close enough for a
dot to be a target rather than a speck — as real geometry that can be hovered and
clicked. This mixin owns what those two gestures mean.

**Hover** is a preview, not an analysis. It reads two MapBiomas years over the
10 km buffer (~0.5 s, measured) and shows what is there now against what was
there in 1985. That is a deliberate limit: a full 40-year, 4-buffer analysis on
hover would be a promise the interface cannot keep while the cursor is moving.

**Click** is the analysis, at the conglomerado's own published coordinates —
unless *multiple selection* is on, in which case a click adds the conglomerado
to a set and the results become the **sum** across all of them. That is why it is
a switch and not a modifier key: it changes what clicking means, and a mode you
can enter by accident is worse than one you have to turn on.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import reflex as rx

from ..config.settings import (
    BUFFER_MODE_DEFAULT, BUFFER_RADII_KM, MULTI_SELECT_MAX_POINTS,
)
from ..services.buffers import buffer_circles_geojson, buffer_geojson
from ..services.mapbiomas_history import (
    aggregate_histories, land_cover_history, preview_land_cover,
)
from ._proxy import plain

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

    # --- multiple selection ------------------------------------------------
    multi_mode: bool = False
    multi_busy: bool = False
    multi_error: str = ""
    #: Display rows for the panel, in click order. Strings only — this crosses
    #: the wire, and nothing in it is used for computation.
    multi_points: list[dict[str, str]] = []

    #: Each selected conglomerado's own buffer history, keyed by point id, kept
    #: so that adding the fifty-first point costs one Earth Engine call rather
    #: than fifty-one — and so that the export reuses exactly the numbers the
    #: chart was drawn from instead of recomputing and possibly differing.
    _multi_frames: dict[str, list[dict[str, Any]]] = {}
    _multi_coords: dict[str, list[float]] = {}
    _multi_meta: dict[str, dict[str, str]] = {}
    _multi_history: list[dict[str, Any]] = []
    _multi_provenance: dict[str, Any] = {}

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
                # Hand the preview back to whatever the cursor was borrowing it
                # from: the multiple selection, or the study point. Blanking the
                # map instead would throw away the view the user built.
                if self.multi_mode:
                    self._apply_multi_view()
                elif self.has_point:
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
                #
                # In multiple-selection mode the hovered buffer is ADDED to the
                # ones already chosen instead of replacing them — previewing one
                # candidate must not blank out the set being built.
                if self.multi_mode:
                    chosen = [list(v) for v in
                              (plain(c) for c in self._multi_coords.values())]
                    if [hover_lat, hover_lon] not in chosen:
                        chosen.append([hover_lat, hover_lon])
                    self._set_preview_many(chosen)
                else:
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
        """What clicking a conglomerado does — which depends on the mode."""
        if self.multi_mode:
            return type(self).toggle_multi_point(props)
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

    # ---------------------------------------------------------------------- #
    # Multiple selection
    # ---------------------------------------------------------------------- #

    def toggle_multi_mode(self, checked: bool):
        """Switch between "click picks a point" and "click adds to a set".

        The selection itself survives being switched off — turning the mode off
        to look at one place, then back on, must not discard an afternoon's
        clicking. Only «Limpar» empties it.
        """
        self.multi_mode = checked
        self.multi_error = ""
        if checked:
            self._apply_multi_view()
        else:
            self._restore_single_view()

    def clear_multi_selection(self):
        self._multi_frames = {}
        self._multi_coords = {}
        self._multi_meta = {}
        self._multi_history = []
        self.multi_points = []
        self.multi_error = ""
        if self.multi_mode:
            self._apply_multi_view()

    @rx.event(background=True)
    async def toggle_multi_point(self, props: dict):
        """Add a conglomerado to the selection, or take it out again.

        Toggling rather than only adding: with a grid this dense, a misclick is
        routine, and the obvious way to undo one is to click it again.
        """
        key = str(props.get("ponto_id") or props.get("conglomerado") or "")
        if not key:
            return

        async with self:
            if key in self._multi_coords:
                self._multi_coords.pop(key, None)
                self._multi_meta.pop(key, None)
                self._multi_frames.pop(key, None)
                self.multi_error = ""
                self._recompute_multi()
                return

            if len(self._multi_coords) >= MULTI_SELECT_MAX_POINTS:
                self.multi_error = (
                    f"Limite de {MULTI_SELECT_MAX_POINTS} conglomerados na "
                    f"seleção. Remova algum para incluir outro."
                )
                return

            try:
                lat, lon = float(props["lat"]), float(props["lon"])
            except (KeyError, TypeError, ValueError):
                self.multi_error = "Coordenadas do conglomerado indisponíveis."
                return

            # The ring and the clipped land cover appear on this click, not on
            # the answer: both are drawn in the browser and owe Earth Engine
            # nothing, so making them wait would be a self-inflicted delay.
            self._multi_coords[key] = [lat, lon]
            self._multi_meta[key] = {
                "key": key,
                "conglomerado": str(props.get("conglomerado", "")),
                "place": " · ".join(str(x) for x in (props.get("municipio"),
                                                     props.get("uf")) if x),
                "bioma": str(props.get("bioma", "")),
            }
            self.multi_error = ""
            self.multi_busy = True
            self._refresh_multi_rows()
            self._apply_multi_view()

        loop = asyncio.get_running_loop()
        try:
            from ..services.geo import point
            df, prov = await loop.run_in_executor(
                None, land_cover_history, point(lat=lat, lon=lon),
                BUFFER_RADII_KM, BUFFER_MODE_DEFAULT,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Multi-select analysis failed for %s: %s", key, exc)
            async with self:
                # Undo the optimistic add: a point drawn on the map but missing
                # from the sum would silently understate every total.
                self._multi_coords.pop(key, None)
                self._multi_meta.pop(key, None)
                self.multi_busy = False
                self.multi_error = f"Falha ao analisar {key}: {exc}"
                self._recompute_multi()
            return

        async with self:
            if key not in self._multi_coords:
                return  # removed again while the query was in flight
            self._multi_frames[key] = df.to_dict("records")
            self._multi_provenance = prov.to_dict()
            self.multi_busy = False
            self._recompute_multi()

    # --- internals ---------------------------------------------------------

    def _recompute_multi(self) -> None:
        """Re-sum the selection and redraw it. Pure pandas, no Earth Engine."""
        import pandas as pd

        frames = [pd.DataFrame(plain(records))
                  for records in self._multi_frames.values()]
        self._multi_history = aggregate_histories(frames).to_dict("records")
        self._refresh_multi_rows()
        if self.multi_mode:
            self._apply_multi_view()

    def _refresh_multi_rows(self) -> None:
        self.multi_points = [
            {**plain(meta),
             # A point still being measured is marked, so a total read while one
             # is outstanding is not mistaken for the final one.
             "pending": "" if key in self._multi_frames else "…"}
            for key, meta in self._multi_meta.items()
        ]

    def _apply_multi_view(self) -> None:
        """Draw every selected conglomerado, with its rings and its land cover."""
        coords = [(lat, lon) for lat, lon in
                  (plain(v) for v in self._multi_coords.values())]
        if not coords:
            self.buffer_overlays = {}
            self._clear_preview()
            return
        self.buffer_overlays = buffer_circles_geojson(coords, BUFFER_RADII_KM)
        self._set_preview_many([[lat, lon] for lat, lon in coords])

    def _restore_single_view(self) -> None:
        """Hand the map back to the study point when the mode is switched off."""
        if not self.has_point:
            self.buffer_overlays = {}
            self._clear_preview()
            return
        from ..services.geo import point
        p = point(lat=self.study_lat, lon=self.study_lon)
        self.buffer_overlays = buffer_geojson(p, BUFFER_RADII_KM,
                                              BUFFER_MODE_DEFAULT)
        self._set_preview(p.lat, p.lon)

    # --- derived -----------------------------------------------------------

    @rx.var
    def multi_count(self) -> int:
        return len(self.multi_points)

    @rx.var
    def multi_active(self) -> bool:
        return self.multi_mode and len(self.multi_points) > 0

    @rx.var
    def multi_label(self) -> str:
        n = len(self.multi_points)
        return f"Soma de {n} conglomerado" + ("" if n == 1 else "s")

    @rx.var
    def multi_conglomerados(self) -> list[str]:
        """Names, for the export."""
        return [str(r.get("conglomerado", "")) for r in self.multi_points
                if r.get("conglomerado")]
