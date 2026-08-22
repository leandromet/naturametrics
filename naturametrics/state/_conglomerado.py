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
from typing import Any, Literal

import reflex as rx

from ..config.settings import (
    BUFFER_MODE_DEFAULT, BUFFER_RADII_KM, MULTI_SELECT_MAX_POINTS,
)
from ..services import ifn as ifn_service
from ..services.buffers import buffer_circles_geojson, buffer_geojson, full_area_geojson
from ..services.vegetation_age import (
    aggregate_forest_age, buffer_forest_age_histogram, full_area_forest_age_histogram,
)
from ..services.mapbiomas_history import (
    aggregate_histories, land_cover_history, preview_land_cover,
    full_area_land_cover_history,
)
from ..services.landscape_metrics import (
    aggregate_landscape_metrics, landscape_metrics, full_area_landscape_metrics,
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
    #: "12/40" while a dragged area is being measured; empty otherwise.
    multi_progress: str = ""
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

    #: Same shape, one key per selected conglomerado — the forest-age histogram
    #: (services.vegetation_age) alongside the land-cover history above. Kept in its
    #: own dict rather than folded into ``_multi_frames`` because the two are
    #: different tables (age bins vs. class/year) summed by different aggregators.
    _multi_age_frames: dict[str, list[dict[str, Any]]] = {}
    _multi_age_history: list[dict[str, Any]] = []
    _multi_age_provenance: dict[str, Any] = {}

    #: Same shape again, for services.landscape_metrics — two dicts per point
    #: rather than one, because the summary rows (patches/LPI/ED/...) and the
    #: class-area histogram behind the diversity indices sum differently (see
    #: aggregate_landscape_metrics: sum/max vs. recomputed-from-pooled-classes).
    _multi_landscape_summaries: dict[str, list[dict[str, Any]]] = {}
    _multi_landscape_histograms: dict[str, list[dict[str, Any]]] = {}
    _multi_landscape_metrics: list[dict[str, Any]] = []
    _multi_landscape_provenance: dict[str, Any] = {}

    #: "sum" (existing, per-point overlap-counted-twice) vs "full_area" (one
    #: bounding box enclosing every selected point's buffer — no overlap, but
    #: it also covers land between clusters). Independent EE computation, so
    #: it is cached and only recomputed on demand, not on every click.
    multi_view_mode: Literal["sum", "full_area"] = "sum"
    multi_bbox_busy: bool = False
    #: landscape metrics is awaited separately from the land-use/age pair
    #: above (compute_full_area) so its own hiccups or extra wall-clock never
    #: hold up a full-area result that already landed — its own busy flag.
    multi_bbox_landscape_busy: bool = False
    #: True whenever the selection has changed since the cached full-area
    #: result was computed — the sum recomputes for free (pure pandas), the
    #: bounding box does not, so it is only paid for again when asked for.
    multi_bbox_stale: bool = True
    _multi_bbox_history: list[dict[str, Any]] = []
    _multi_bbox_age_history: list[dict[str, Any]] = []
    _multi_bbox_provenance: dict[str, Any] = {}
    _multi_bbox_age_provenance: dict[str, Any] = {}
    _multi_bbox_landscape_metrics: list[dict[str, Any]] = []
    _multi_bbox_landscape_provenance: dict[str, Any] = {}
    #: full_area_geojson() output, drawn on the map instead of the per-point
    #: rings while multi_view_mode == "full_area".
    _multi_bbox_overlay: dict[str, Any] = {}

    @rx.event(background=True)
    async def preview_conglomerado(self, props: dict):
        """Fill the hover card for one conglomerado, or clear it.

        The hook sends ``{}`` when the cursor leaves, after a grace period.
        This is the single callback every browser-side point layer's hover
        funnels into (pages/index.py wires it once); a pasted coordinate list
        replacing the IFN layer on screen (state/_user_points.py) means it
        replaces it here too, before any conglomerado-shaped assumption runs —
        a user point's props carry ``id``, not ``conglomerado``.
        """
        if self.user_points_active:
            # NOT `type(self).preview_user_point(props)`: that dispatch pattern
            # (used below and in select_conglomerado) builds an EventSpec off
            # `type(self)`, which only works from a plain, non-background
            # handler — inside a background one `self` is a StateProxy, and
            # `type(self)` is `StateProxy` itself, with no such attribute. A
            # background handler calling another background handler's logic
            # has to do it as a direct awaited call instead.
            return await self._preview_user_point(props)
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
                    self.hover_error = self.tr["hover_coords_unavailable"]
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
                    self.hover_error = self.tr["hover_read_failed"]
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
            self.hover_note = self.tr["hover_no_coverage"]
            return
        name_col = "class_pt" if self.language == "pt" else "class_en"
        pt_decimal = self.language == "pt"
        self.hover_rows = [
            {"name": str(r.get(name_col, r["class_pt"])), "color": str(r["color"]),
             "pct": (f"{r['pct']:.1f}%".replace(".", ",") if pt_decimal
                     else f"{r['pct']:.1f}%")
                    if "pct" in r else str(r["pct_label"]),
             # Signed and in percentage points, with the sign kept for zero-ish
             # values so the column reads as a change column, not a second share.
             "delta": ("+" if r["delta"] > 0 else "") +
                      (f"{r['delta']:.1f}".replace(".", ",") if pt_decimal
                       else f"{r['delta']:.1f}") + " pp"}
            for r in preview["rows"]
        ]
        first, last = preview["natural_first"], preview["natural_last"]
        first_s = str(first).replace(".", ",") if pt_decimal else str(first)
        last_s = str(last).replace(".", ",") if pt_decimal else str(last)
        self.hover_natural = self.tr["hover_natural_template"].format(
            last=last_s, first=first_s, year=preview["first_year"])
        self.hover_note = self.tr["hover_note_template"].format(
            year=preview["last_year"], radius=f"{preview['radius_km']:g}")

    def select_conglomerado(self, props: dict):
        """What clicking a conglomerado does — which depends on the mode.

        Same funnel as preview_conglomerado above: a pasted list active means
        this click is on one of ITS points, not an IFN conglomerado.
        """
        if self.user_points_active:
            return type(self).select_user_point(props)
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
    # A pasted coordinate list, standing in for the IFN layer above
    # ---------------------------------------------------------------------- #

    async def _preview_user_point(self, props: dict):
        """Hover card for a point from a pasted list.

        A plain async method, not ``@rx.event`` — it only exists to be called
        directly from inside preview_conglomerado's background task (see the
        note there on why), never dispatched as its own event from the
        frontend, which never references it by name.

        Same card, same preview call as preview_conglomerado — deliberately: the
        point is that switching the data source should not feel like switching
        features. No multi-selection interplay, because a pasted list is not
        built by clicking one point at a time the way the IFN grid is.
        """
        if not props or props.get("id") is None:
            async with self:
                self._hover_token += 1
                self.hover_visible = False
                self.hover_loading = False
                if self.has_point:
                    self._set_preview(self.study_lat, self.study_lon)
                else:
                    self._clear_preview()
            return

        key = str(props.get("id"))
        try:
            lat, lon = float(props["lat"]), float(props["lon"])
        except (KeyError, TypeError, ValueError):
            return

        async with self:
            self._hover_token += 1
            token = self._hover_token
            self._set_preview(lat, lon)
            self.hover_visible = True
            self.hover_conglomerado = key
            self.hover_place = ""
            self.hover_bioma = ""
            self.hover_error = ""
            cache_key = f"user:{key}"
            cached = self._preview_cache.get(cache_key)
            if cached is not None:
                self._apply_preview(cached)
                return
            self.hover_loading = True
            self.hover_rows = []
            self.hover_natural = ""

        if self.mapbiomas_year not in self._mb_urls:
            await self._ensure_year(self.mapbiomas_year)

        loop = asyncio.get_running_loop()
        try:
            from ..services.geo import point
            preview = await loop.run_in_executor(
                None, preview_land_cover, point(lat=lat, lon=lon))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Preview failed for user point %s: %s", key, exc)
            async with self:
                if token == self._hover_token:
                    self.hover_loading = False
                    self.hover_error = self.tr["hover_read_failed"]
            return

        async with self:
            if len(self._preview_cache) >= _PREVIEW_CACHE_MAX:
                self._preview_cache.clear()
            self._preview_cache[cache_key] = preview
            if token != self._hover_token:
                return
            self._apply_preview(preview)

    def select_user_point(self, props: dict):
        """Clicking a pasted point sets it as the study point, named by
        whatever the pasted line's own id was — the same identity that will
        appear in the export, not an anonymous coordinate."""
        try:
            lat, lon = float(props["lat"]), float(props["lon"])
        except (KeyError, TypeError, ValueError):
            logger.warning("User point click without usable coordinates: %s", props)
            return

        event = self.set_study_point(lat, lon)
        if not self.has_point:
            return event

        self.point_source = "lista enviada pelo usuário"
        self.point_conglomerado = str(props.get("id", ""))
        self.point_uf = ""
        self.point_municipio = ""
        self.point_bioma = ""
        self.hover_visible = False
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
        # The drawer shows analysis_error *instead of* the chart, so a failure
        # left over from an earlier single point would hide the sum.
        self.analysis_error = ""
        self.point_error = ""
        if checked and self.user_points_active:
            # Only one point-source mode drives the map's hover/click at a
            # time. Deactivated, not reset — the pasted list itself is not
            # discarded, only its claim on the interactive layer.
            self.user_points_active = False
            self._refresh_layers()
        if checked:
            self._apply_multi_view()
        else:
            # Re-entering multi mode later should start from the cheap,
            # already-current sum rather than silently reusing a full-area
            # result that may no longer match whatever gets selected next.
            self.multi_view_mode = "sum"
            self._restore_single_view()

    def clear_multi_selection(self):
        self._multi_frames = {}
        self._multi_age_frames = {}
        self._multi_landscape_summaries = {}
        self._multi_landscape_histograms = {}
        self._multi_landscape_metrics = []
        self._multi_coords = {}
        self._multi_meta = {}
        self._multi_history = []
        self._multi_age_history = []
        self._multi_bbox_history = []
        self._multi_bbox_age_history = []
        self._multi_bbox_landscape_metrics = []
        self._multi_bbox_overlay = {}
        self.multi_view_mode = "sum"
        self.multi_bbox_stale = True
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
                self._multi_age_frames.pop(key, None)
                self._multi_landscape_summaries.pop(key, None)
                self._multi_landscape_histograms.pop(key, None)
                self.multi_error = ""
                self._recompute_multi()
                return

            if len(self._multi_coords) >= MULTI_SELECT_MAX_POINTS:
                self.multi_error = self.tr["multi_limit_reached"].format(
                    max=MULTI_SELECT_MAX_POINTS)
                return

            try:
                lat, lon = float(props["lat"]), float(props["lon"])
            except (KeyError, TypeError, ValueError):
                self.multi_error = self.tr["hover_coords_unavailable"]
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
        from ..services.geo import point
        p = point(lat=lat, lon=lon)
        # Issued together, not one after the other: all three are independent
        # Earth Engine round-trips for the same point, so the trio costs one
        # wall-clock wait rather than three (same reasoning as run_analysis).
        # landscape_metrics is awaited through its own try/except below,
        # separately from history/age — it has no retry ladder and fails more
        # often (services/landscape_metrics.py), and that must not evict a
        # point whose land-use/age sum otherwise worked fine.
        history_task = loop.run_in_executor(
            None, land_cover_history, p, BUFFER_RADII_KM,
            BUFFER_MODE_DEFAULT, self.buffer_shape)
        age_task = loop.run_in_executor(
            None, buffer_forest_age_histogram, p, BUFFER_RADII_KM,
            BUFFER_MODE_DEFAULT, self.buffer_shape)
        metrics_task = loop.run_in_executor(
            None, landscape_metrics, p, BUFFER_RADII_KM,
            BUFFER_MODE_DEFAULT, self.buffer_shape)

        try:
            (df, prov), (age_df, age_prov) = await asyncio.gather(history_task, age_task)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Multi-select analysis failed for %s: %s", key, exc)
            async with self:
                # Undo the optimistic add: a point drawn on the map but missing
                # from the sum would silently understate every total.
                self._multi_coords.pop(key, None)
                self._multi_meta.pop(key, None)
                self.multi_busy = False
                self.multi_error = self.tr["multi_analysis_failed"].format(
                    key=key, exc=exc)
                self._recompute_multi()
            return

        async with self:
            if key not in self._multi_coords:
                return  # removed again while the query was in flight
            self._multi_frames[key] = df.to_dict("records")
            self._multi_provenance = prov.to_dict()
            self._multi_age_frames[key] = age_df.to_dict("records")
            self._multi_age_provenance = age_prov.to_dict()
            self.multi_busy = False
            self._recompute_multi()

        try:
            metrics_summary, metrics_hist, metrics_prov = await metrics_task
        except Exception as exc:  # noqa: BLE001
            logger.warning("Multi-select landscape metrics failed for %s: %s", key, exc)
            return  # the point stays selected; it just has no metrics to sum

        async with self:
            if key in self._multi_coords:
                self._multi_landscape_summaries[key] = metrics_summary.to_dict("records")
                self._multi_landscape_histograms[key] = metrics_hist.to_dict("records")
                self._multi_landscape_provenance = metrics_prov.to_dict()
                self._recompute_multi()

    @rx.event(background=True)
    async def select_multi_area(self, bounds: dict):
        """Add every conglomerado inside a dragged box.

        Resolved from the local point table under the *current map filters*, so
        the box selects what the map is showing and not the conglomerados hidden
        by a filter — a rectangle that quietly picked up points the user cannot
        see would be a trap.
        """
        if not self.multi_mode:
            return
        try:
            west, south = float(bounds["west"]), float(bounds["south"])
            east, north = float(bounds["east"]), float(bounds["north"])
        except (KeyError, TypeError, ValueError):
            return

        async with self:
            # Each drag-select is a fresh area, not an addition to whatever was
            # selected before — merging two far-apart boxes would silently
            # inflate the selection into a country-spanning blob, and with it
            # the full-area bounding box (services.buffers.full_area_bbox)
            # that has to enclose everything still in the set. Clearing here
            # mirrors clear_multi_selection exactly, short of leaving multi
            # mode itself.
            self._multi_frames = {}
            self._multi_age_frames = {}
            self._multi_landscape_summaries = {}
            self._multi_landscape_histograms = {}
            self._multi_landscape_metrics = []
            self._multi_coords = {}
            self._multi_meta = {}
            self._multi_history = []
            self._multi_age_history = []
            self._multi_bbox_history = []
            self._multi_bbox_age_history = []
            self._multi_bbox_landscape_metrics = []
            self._multi_bbox_overlay = {}
            self.multi_view_mode = "sum"
            self.multi_bbox_stale = True
            self.multi_points = []
            region, uf = self.ifn_region, self.ifn_uf
            municipality, biome = self.ifn_municipality, self.ifn_biome
            existing = set(self._multi_coords)
            room = MULTI_SELECT_MAX_POINTS - len(existing)

        found = ifn_service.points_in_bbox(
            west, south, east, north, region=region, uf=uf,
            municipality=municipality, biome=biome,
            limit=MULTI_SELECT_MAX_POINTS,
        )["features"]

        fresh = [f["properties"] for f in found
                 if str(f["properties"]["ponto_id"]) not in existing]
        if not fresh:
            async with self:
                self.multi_error = (
                    self.tr["multi_area_none_new"] if found
                    else self.tr["multi_area_none"]
                )
            return

        truncated = len(fresh) > room
        fresh = fresh[:max(room, 0)]
        if not fresh:
            async with self:
                self.multi_error = self.tr["multi_area_limit_reached"].format(
                    max=MULTI_SELECT_MAX_POINTS)
            return

        async with self:
            for props in fresh:
                key = str(props["ponto_id"])
                self._multi_coords[key] = [float(props["lat"]), float(props["lon"])]
                self._multi_meta[key] = {
                    "key": key,
                    "conglomerado": str(props.get("conglomerado", "")),
                    "place": " · ".join(str(x) for x in (props.get("municipio"),
                                                         props.get("uf")) if x),
                    "bioma": str(props.get("bioma", "")),
                }
            self.multi_busy = True
            self.multi_error = (
                self.tr["multi_area_truncated"].format(n=len(fresh))
                if truncated else ""
            )
            self._refresh_multi_rows()
            self._apply_multi_view()

        # Fanned out rather than looped: the pool is sized for this, and a box
        # over a dense municipality is dozens of points that would otherwise be
        # dozens of sequential round-trips.
        from ..services.ee_concurrency import get_ee_executor
        from ..services.geo import point

        executor = get_ee_executor()
        progress = {"done": 0}

        def _history_and_age(p):
            """Both tables for one point, sequentially in one pool thread.

            One future per point rather than two keeps the done/bad bookkeeping
            below unchanged from before forest age existed, at the cost of a
            point's own wall time being the sum of the two calls rather than the
            max — acceptable here because points still run in parallel against
            each other across the pool, which is what actually bounds a box
            select's total time.
            """
            df, prov = land_cover_history(
                p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, shape=self.buffer_shape)
            age_df, age_prov = buffer_forest_age_histogram(
                p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, shape=self.buffer_shape)
            return df, prov, age_df, age_prov

        def collect():
            """Submit every point, then gather. One thread, not one per point.

            Awaiting each future individually through ``run_in_executor`` would
            take a thread from the default pool *per conglomerado* just to sit
            and wait, and a box over a dense município would exhaust it. The
            Earth Engine pool is the one doing the work; this only harvests.
            """
            futures = {
                executor.submit(_history_and_age,
                                point(lat=row["lat"], lon=row["lon"])):
                str(row["ponto_id"]) for row in fresh
            }
            done: dict[str, Any] = {}
            bad: list[str] = []
            for future in futures:
                key = futures[future]
                try:
                    df, prov, age_df, age_prov = future.result(timeout=180)
                    done[key] = (df.to_dict("records"), prov.to_dict(),
                                 age_df.to_dict("records"), age_prov.to_dict())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Area select failed for %s: %s", key, exc)
                    bad.append(key)
                progress["done"] += 1
            return done, bad

        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, collect)
        while not task.done():
            await asyncio.sleep(0.4)
            async with self:
                self.multi_progress = f"{progress['done']}/{len(fresh)}"
        results, failed = await task

        async with self:
            self.multi_progress = ""
            for key, (records, prov, age_records, age_prov) in results.items():
                if key in self._multi_coords:
                    self._multi_frames[key] = records
                    self._multi_provenance = prov
                    self._multi_age_frames[key] = age_records
                    self._multi_age_provenance = age_prov
            for key in failed:
                # Same rule as a single click: a point on the map but absent
                # from the sum would understate every total.
                self._multi_coords.pop(key, None)
                self._multi_meta.pop(key, None)
            if failed and not self.multi_error:
                self.multi_error = self.tr["multi_area_failed"].format(n=len(failed))
            self.multi_busy = False
            self._recompute_multi()

        # A second, separate fan-out over whichever points survived the pass
        # above — landscape_metrics has no retry ladder and fails more often
        # than history/age (services/landscape_metrics.py), so it is not
        # allowed a vote on whether a point stays selected; it only adds to
        # the sum when it succeeds.
        surviving = [row for row in fresh if str(row["ponto_id"]) not in failed]
        if surviving:
            def collect_metrics():
                futures = {
                    executor.submit(
                        landscape_metrics, point(lat=row["lat"], lon=row["lon"]),
                        BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, self.buffer_shape):
                    str(row["ponto_id"]) for row in surviving
                }
                done: dict[str, Any] = {}
                for future in futures:
                    key = futures[future]
                    try:
                        summary_df, hist_df, prov = future.result(timeout=180)
                        done[key] = (summary_df.to_dict("records"),
                                     hist_df.to_dict("records"), prov.to_dict())
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Area select landscape metrics failed for %s: %s",
                            key, exc)
                return done

            metrics_results = await loop.run_in_executor(None, collect_metrics)
            async with self:
                for key, (summary_records, hist_records, prov) in metrics_results.items():
                    if key in self._multi_coords:
                        self._multi_landscape_summaries[key] = summary_records
                        self._multi_landscape_histograms[key] = hist_records
                        self._multi_landscape_provenance = prov
                if metrics_results:
                    self._recompute_multi()

    # --- internals ---------------------------------------------------------

    def _recompute_multi(self) -> None:
        """Re-sum the selection and redraw it. Pure pandas, no Earth Engine."""
        import pandas as pd

        frames = [pd.DataFrame(plain(records))
                  for records in self._multi_frames.values()]
        self._multi_history = aggregate_histories(frames).to_dict("records")
        age_frames = [pd.DataFrame(plain(records))
                      for records in self._multi_age_frames.values()]
        self._multi_age_history = aggregate_forest_age(age_frames).to_dict("records")
        landscape_summaries = [pd.DataFrame(plain(records))
                               for records in self._multi_landscape_summaries.values()]
        landscape_histograms = [pd.DataFrame(plain(records))
                                for records in self._multi_landscape_histograms.values()]
        self._multi_landscape_metrics = aggregate_landscape_metrics(
            landscape_summaries, landscape_histograms).to_dict("records")
        # The cached full-area result was computed for the selection as it
        # stood before this add/remove — it no longer describes what is on
        # screen, so it is marked stale rather than silently left to look current.
        self.multi_bbox_stale = True
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
        """Draw every selected conglomerado, with its rings and its land cover.

        In full-area mode, once a bounding box has actually been computed, the
        rectangles replace the per-point rings — that is the region the chart
        is reading, and the map should show the same thing.
        """
        coords = [(lat, lon) for lat, lon in
                  (plain(v) for v in self._multi_coords.values())]
        if not coords:
            self.buffer_overlays = {}
            self._clear_preview()
            return
        if self.multi_view_mode == "full_area" and self._multi_bbox_overlay:
            self.buffer_overlays = plain(self._multi_bbox_overlay)
        else:
            self.buffer_overlays = buffer_circles_geojson(
                coords, BUFFER_RADII_KM, shape=self.buffer_shape)
        self._set_preview_many([[lat, lon] for lat, lon in coords])

    # --- full-area (bounding box) view --------------------------------- #

    def set_multi_view_mode(self, value: str | list[str]):
        """Switch between "sum" and "full_area" for the charts and the map.

        The sum is always ready (pure pandas, recomputed on every add/remove);
        full-area is a real Earth Engine round-trip, so switching to it kicks
        off the computation only if the cache is empty or stale, rather than
        on every selection change.
        """
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        mode = "full_area" if str(raw) == self.tr["multi_view_full_area"] else "sum"
        self.multi_view_mode = mode
        if mode == "full_area" and (self.multi_bbox_stale or not self._multi_bbox_history):
            return type(self).compute_full_area()
        self._apply_multi_view()

    @rx.event(background=True)
    async def compute_full_area(self):
        """The bounding-box equivalent of the per-point sum, computed once for
        whatever is currently selected — not fanned out, since this is one EE
        call per table rather than one per point."""
        async with self:
            coords = [(lat, lon) for lat, lon in
                      (plain(v) for v in self._multi_coords.values())]
            if not coords:
                return
            self.multi_bbox_busy = True
            self.multi_bbox_landscape_busy = True
            self.multi_error = ""
            shape = self.buffer_shape

        loop = asyncio.get_running_loop()
        from ..services.geo import point
        pts = [point(lat=lat, lon=lon) for lat, lon in coords]
        history_task = loop.run_in_executor(
            None, full_area_land_cover_history, pts, BUFFER_RADII_KM, shape)
        age_task = loop.run_in_executor(
            None, full_area_forest_age_histogram, pts, BUFFER_RADII_KM, shape)
        # Awaited through its own try/except below — a landscape-metrics
        # hiccup must not blank the land-use/age full-area result it rides
        # alongside (same reasoning as run_analysis and toggle_multi_point).
        metrics_task = loop.run_in_executor(
            None, full_area_landscape_metrics, pts, BUFFER_RADII_KM, shape)

        try:
            (df, prov), (age_df, age_prov) = await asyncio.gather(history_task, age_task)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Full-area computation failed: %s", exc)
            async with self:
                self.multi_bbox_busy = False
                self.multi_bbox_landscape_busy = False
                self.multi_error = self.tr["multi_full_area_failed"].format(exc=exc)
            return

        async with self:
            self._multi_bbox_history = df.to_dict("records")
            self._multi_bbox_provenance = prov.to_dict()
            self._multi_bbox_age_history = age_df.to_dict("records")
            self._multi_bbox_age_provenance = age_prov.to_dict()
            self._multi_bbox_overlay = full_area_geojson(pts, BUFFER_RADII_KM, shape)
            self.multi_bbox_stale = False
            self.multi_bbox_busy = False
            if self.multi_mode:
                self._apply_multi_view()

        try:
            metrics_summary, _metrics_hist, metrics_prov = await metrics_task
        except Exception as exc:  # noqa: BLE001
            logger.warning("Full-area landscape metrics failed: %s", exc)
            async with self:
                self.multi_bbox_landscape_busy = False
            return

        async with self:
            self._multi_bbox_landscape_metrics = metrics_summary.to_dict("records")
            self._multi_bbox_landscape_provenance = metrics_prov.to_dict()
            self.multi_bbox_landscape_busy = False

    def _restore_single_view(self) -> None:
        """Hand the map back to the study point when the mode is switched off."""
        if not self.has_point:
            self.buffer_overlays = {}
            self._clear_preview()
            return
        from ..services.geo import point
        p = point(lat=self.study_lat, lon=self.study_lon)
        self.buffer_overlays = buffer_geojson(
            p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, self.buffer_shape)
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
        return self.tr["multi_label_one" if n == 1 else "multi_label_many"].format(n=n)

    @rx.var
    def multi_conglomerados(self) -> list[str]:
        """Names, for the export."""
        return [str(r.get("conglomerado", "")) for r in self.multi_points
                if r.get("conglomerado")]

    @rx.var
    def multi_view_options(self) -> list[str]:
        return [self.tr["multi_view_sum"], self.tr["multi_view_full_area"]]

    @rx.var
    def multi_view_value(self) -> str:
        return (self.tr["multi_view_full_area"] if self.multi_view_mode == "full_area"
                else self.tr["multi_view_sum"])

    @rx.var
    def multi_bbox_loading(self) -> bool:
        return self.multi_view_mode == "full_area" and self.multi_bbox_busy

    @rx.var
    def multi_bbox_any_loading(self) -> bool:
        """Whether *any* of the three full-area tables — land-use, age,
        landscape metrics — is still being computed. Drives the shared
        Soma/Área total toggle's spinner (results.py _multi_view_toggle),
        which is not scoped to one panel the way multi_bbox_loading is."""
        return self.multi_view_mode == "full_area" and (
            self.multi_bbox_busy or self.multi_bbox_landscape_busy)

    @rx.var
    def full_area_active(self) -> bool:
        """Full-area mode, with a selection to show it for — gates the radius
        selector swap in results.py: full area reads only the single outer
        box (services.buffers.full_area_bbox), so there is no radius to pick."""
        return self.multi_active and self.multi_view_mode == "full_area"
