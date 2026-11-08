"""Map layer state for the world page.

Same shape as the Brazil page's layer state and for the same reason: the layer
list is plain state rather than a computed var, because building it can require
minting Earth Engine tile URLs and a computed var would re-run that on every
read.

Toggleable Earth Engine layers, each independent: GLC-FCS30D land cover for one year (in tile
groups: the page opens with two and adds the others on request or when a click needs one), Hansen
tree cover, the Hansen loss/gain mask, the year of the last loss and of the last burn —
plus the annual Landsat composite, which behaves as an *overlay on* the chosen
base map rather than a base map of its own (same as Brazil's SPOT mosaics).

``map_vectors`` is the browser-fetched counterpart to ``map_layers`` above —
GBIF is the first (and so far only) USA-page layer that belongs there
rather than in ``map_layers``, since Leaflet fetches it itself rather than the
server minting a tile URL. See the Brazil page's ``state/_layers.py::
_build_vectors`` for the layer this one is modelled on.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import reflex as rx

from ...config.settings import (
    BUFFER_PREVIEW_OPACITY, BUFFER_PREVIEW_RADIUS_KM, BUFFER_PREVIEW_SHAPE,
)
from ...services.ee_client import get_ee
from ..config import glc
from ..config import datasets as ds
from ..config import forest as fc_cfg
from ..config import settings as ca_st
from ..services import gbif as gbif_service
from ..services import glc_earth
from ..services import layers as layer_service

logger = logging.getLogger(__name__)


class WorldLayersMixin(rx.State, mixin=True):
    """Which layers are on the map, and what the map is showing."""

    # --- view -------------------------------------------------------------
    map_center: list[float] = [ca_st.MAP_CENTER[0], ca_st.MAP_CENTER[1]]
    map_zoom: int = ca_st.MAP_ZOOM
    map_bounds: list[list[float]] = [list(ca_st.WORLD_VIEW_BOUNDS[0]),
                                     list(ca_st.WORLD_VIEW_BOUNDS[1])]
    #: ``[[s, w], [n, e]]`` re-applied imperatively whenever it changes; empty
    #: means "leave the viewport alone". Initial framing is ``map_bounds`` above.
    #: The Brazil page drives this from its IFN filters; the USA page has no
    #: filter-driven re-framing, so it stays empty and the user keeps their view.
    fit_bounds: list[list[float]] = []

    map_layers: list[dict[str, Any]] = []
    buffer_overlays: dict[str, Any] = {}
    map_vectors: list[dict[str, Any]] = []

    # --- base map ---------------------------------------------------------
    basemap: str = ds.DEFAULT_BASEMAP
    basemap_error: str = ""

    # --- GLC land cover ---------------------------------------------------
    show_glc: bool = False
    #: The tile groups loaded (the page opens with Brazil's and Africa's); the others on request, or
    #: when a click falls in one (the magnifier needs that group's tiles).
    glc_groups: list[str] = list(layer_service.START_GROUPS)
    glc_year: int = glc.GLC_YEAR_END
    glc_opacity: float = 0.75
    #: Swipe comparison of two GLC years: the baseline (``compare_year``, default the oldest) on the left
    #: of the divider, the active ``glc_year`` (default the newest) on the right.
    compare_on: bool = False
    compare_year: int = glc.GLC_YEAR_START

    # --- buffer preview ("magnifying glass") ------------------------------
    #: Shows the crop inventory *only inside* the analysis radius around the
    #: clicked point, and nowhere else. Costs no Earth Engine call: the tile URL
    #: is minted once at startup and the restriction to a circle is a CSS clip
    #: applied in the browser (see leaflet_map.js).
    #:
    #: Always the **most recent** GLC year rather than whatever the year slider
    #: happens to be on — the magnifier answers "what is here now", and pairing
    #: it with a slider the user moved for a different purpose would make it
    #: quietly disagree with itself.
    show_buffer_preview: bool = True
    preview_points: list[list[float]] = []

    # --- disturbance and fire (Hansen loss year, MODIS burn year) ---------
    show_loss_year: bool = False
    show_burn_year: bool = False

    # --- Hansen -----------------------------------------------------------
    show_treecover: bool = False
    treecover_opacity: float = 0.6
    show_change: bool = False
    change_from_year: int = fc_cfg.HANSEN_LOSS_YEAR_START
    treecover_threshold: int = fc_cfg.HANSEN_TREECOVER_THRESHOLD

    # --- Landsat ----------------------------------------------------------
    show_landsat: bool = False
    landsat_rendering: str = "landsat_true"
    landsat_year: int = 2024

    # --- engine status ----------------------------------------------------
    ee_ready: bool = False
    ee_error: str = ""
    layer_busy: bool = False

    #: Minted tile URLs, keyed by layer id. Kept so a toggle that has already
    #: been on once repaints with no round-trip at all.
    _url_cache: dict[str, str] = {}

    # ---------------------------------------------------------------------- #
    # Layer assembly
    # ---------------------------------------------------------------------- #

    def _build_layers(self) -> list[dict[str, Any]]:
        """Assemble the ordered layer list from the current selections."""
        specs: list[dict[str, Any]] = []

        base = layer_service.basemap_spec(self.basemap, z_index=0)
        if base:
            specs.append(base)

        for key, spec in self._cached_specs():
            if spec:
                specs.append(spec)
        return specs

    def _glc_lids(self, year: int) -> list[tuple[str, str, int]]:
        """(layer id, group, year drawn) for every loaded tile group at a year (snapped to the series)."""
        y = glc.nearest_year("world", year)
        return [(layer_service.glc_lid(y, g), g, y) for g in self.glc_groups]

    def _cached_specs(self):
        """Yield (id, spec) for every enabled Earth Engine layer.

        Reads only ``_url_cache``; nothing here mints. Minting happens in the
        background events below, which then call ``_refresh_layers``.
        """
        if self.show_landsat:
            lid = f"world:landsat:{self.landsat_rendering}:{self.landsat_year}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": 1.0,
                    "attribution": f"{ds.LANDSAT_ATTRIBUTION} — {self.landsat_year}",
                    "z_index": 1, "max_native_zoom": 14,
                }

        if self.show_glc:
            for lid, _g, drawn in self._glc_lids(self.glc_year):
                url = self._url_cache.get(lid)
                if url:
                    yield lid, {
                        "id": lid, "url": url, "opacity": self.glc_opacity,
                        "attribution": f"{layer_service.GLC_ATTRIBUTION} {drawn}",
                        "z_index": 10, "max_native_zoom": 15,
                        "clip": "right" if self.compare_on else None,
                    }
            if self.compare_on:
                for lid_b, _g, drawn_b in self._glc_lids(self.compare_year):
                    url_b = self._url_cache.get(lid_b)
                    if url_b:
                        yield f"{lid_b}:cmp", {
                            "id": f"{lid_b}:cmp", "url": url_b, "opacity": self.glc_opacity,
                            "attribution": f"{layer_service.GLC_ATTRIBUTION} {drawn_b}",
                            "z_index": 11, "max_native_zoom": 15, "clip": "left",
                        }

        # Suppressed while the full GLC layer is on — the coverage is already
        # painted across the whole map, so a magnifier over it shows nothing new.
        if self.show_buffer_preview and self.preview_points and not self.show_glc:
            for lid, _g, drawn in self._glc_lids(glc.GLC_YEAR_END):
                url = self._url_cache.get(lid)
                if url:
                    yield f"world:preview:{lid}", {
                        "id": f"world:preview:{lid}",
                        "url": url,
                        "opacity": BUFFER_PREVIEW_OPACITY,
                        "attribution": f"{layer_service.GLC_ATTRIBUTION} {drawn}",
                        "z_index": 13, "max_native_zoom": 15,
                        "clip_circles": [{"lat": lat, "lon": lon}
                                         for lat, lon in self.preview_points],
                        "clip_radius_km": BUFFER_PREVIEW_RADIUS_KM,
                        "clip_shape": BUFFER_PREVIEW_SHAPE,
                    }

        if self.show_loss_year:
            lid = "world:loss_year"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {"id": lid, "url": url, "opacity": 0.8,
                            "attribution": f"{layer_service.HANSEN_ATTRIBUTION} — most recent tree-cover loss year",
                            "z_index": 12, "max_native_zoom": 15}
        if self.show_burn_year:
            lid = "world:burn_year"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {"id": lid, "url": url, "opacity": 0.8,
                            "attribution": "NASA — MODIS MCD64A1 burned area: most recent burn year",
                            "z_index": 13, "max_native_zoom": 12}

        if self.show_treecover:
            lid = f"world:hansen_tc:{self.treecover_threshold}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": self.treecover_opacity,
                    "attribution": layer_service.HANSEN_ATTRIBUTION,
                    "z_index": 11, "max_native_zoom": 15,
                }

        if self.show_change:
            lid = f"world:hansen_change:{self.change_from_year}:{self.treecover_threshold}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": 0.85,
                    "attribution": layer_service.HANSEN_ATTRIBUTION,
                    "z_index": 20, "max_native_zoom": 15,
                }

    def _refresh_layers(self) -> None:
        self.map_layers = self._build_layers()
        self.map_vectors = self._build_vectors()

    def _build_vectors(self) -> list[dict[str, Any]]:
        """Layers the browser fetches and draws itself, in stacking order.

        Just GBIF for now — the Brazil page's own ``_build_vectors`` also
        carries biomes/embargos/auto_infracao/IFN, none of which have a
        USA-page equivalent yet.
        """
        specs: list[dict[str, Any]] = []
        if self.show_gbif:
            # emit_meta asks the map to report the fetch's own counts back
            # (WorldGbifMixin.on_gbif_layer_meta) — same reasoning as the
            # Brazil page: at zoom 10 a viewport can hold far more occurrences
            # than the 300-record page returns, and the panel has to say so.
            spec = gbif_service.vector_spec(self.gbif_filters,
                                            opacity=self.gbif_opacity)
            spec["emit_meta"] = True
            specs.append(spec)
        return specs

    # ---------------------------------------------------------------------- #
    # Initialisation
    # ---------------------------------------------------------------------- #

    @rx.event(background=True)
    async def initialise(self):
        """Connect to Earth Engine and paint the base map.

        The base map is seeded synchronously first so the very first frame has
        tiles, then Earth Engine is contacted — the same ordering the Brazil
        page uses so a slow or failed EE connection never leaves a blank map.
        """
        async with self:
            if not self.map_layers:
                self._refresh_layers()
            if self.ee_ready:
                return

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, get_ee)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Earth Engine initialisation failed")
            async with self:
                self.ee_error = str(exc)
            return

        async with self:
            self.ee_ready = True
            self.ee_error = ""
            self._refresh_layers()

        # Warm the magnifier's tile URL now rather than on the first click. It
        # is one call, and paying for it here means the clipped preview appears
        # with the click instead of a second later — which is the whole point of
        # a layer that owes Earth Engine nothing at click time.
        for lid, group, year in self._glc_lids(glc.GLC_YEAR_END):
            await self._mint(lid, lambda g=group, y=year: layer_service.glc_spec(y, g))

    @rx.event(background=True)
    async def warm_point_group(self, lat: float, lon: float):
        """Make sure the tile group holding the clicked point is loaded (the magnifier needs it), and
        mint its latest-year tile. Adds the group to ``glc_groups`` when the page opened without it."""
        group = glc_earth.group_of(lon)
        async with self:
            if group not in self.glc_groups:
                self.glc_groups = [*self.glc_groups, group]
            self._refresh_layers()
            year = glc.GLC_YEAR_END
            cmp_on, cmp_year = self.compare_on, self.compare_year
            loss_on, burn_on = self.show_loss_year, self.show_burn_year
        await self._mint(layer_service.glc_lid(year, group), lambda: layer_service.glc_spec(year, group))
        if cmp_on:
            y = glc.nearest_year("world", cmp_year)
            await self._mint(layer_service.glc_lid(y, group), lambda: layer_service.glc_spec(y, group))
        if loss_on:
            await self._mint("world:loss_year", layer_service.loss_year_spec)
        if burn_on:
            await self._mint("world:burn_year", layer_service.burn_spec)

    @rx.event(background=True)
    async def load_east(self):
        """Add the Asia and Australasia tile groups (the page opens without them)."""
        async with self:
            self.glc_groups = list(layer_service.GROUPS)
            self._refresh_layers()
            year, cmp_on, cmp_year, on = self.glc_year, self.compare_on, self.compare_year, self.show_glc
        if on:
            for lid, g, y in self._glc_lids(year):
                await self._mint(lid, lambda g=g, y=y: layer_service.glc_spec(y, g))
            if cmp_on:
                for lid, g, y in self._glc_lids(cmp_year):
                    await self._mint(lid, lambda g=g, y=y: layer_service.glc_spec(y, g))

    def _set_preview(self, lat: float, lon: float) -> None:
        """Point the magnifier at one location."""
        self.preview_points = [[float(lat), float(lon)]]
        self._refresh_layers()

    def _clear_preview(self) -> None:
        self.preview_points = []
        self._refresh_layers()

    def toggle_buffer_preview(self, checked: bool):
        self.show_buffer_preview = checked
        self._refresh_layers()

    async def _mint(self, layer_id: str, builder) -> None:
        """Mint one tile URL off the event loop and repaint.

        ``builder`` is a zero-argument callable returning a layer spec; it runs
        in the executor because ``getMapId`` is a blocking network call.
        """
        if layer_id in self._url_cache:
            async with self:
                self._refresh_layers()
            return

        async with self:
            self.layer_busy = True
            self._refresh_layers()

        loop = asyncio.get_running_loop()
        try:
            spec = await loop.run_in_executor(None, builder)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Minting %s failed: %s", layer_id, exc)
            spec = None

        async with self:
            self.layer_busy = False
            if spec and spec.get("url"):
                self._url_cache[layer_id] = spec["url"]
            self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Event handlers
    # ---------------------------------------------------------------------- #

    def set_basemap(self, key: str | list[str]):
        raw = key[0] if isinstance(key, (list, tuple)) and key else key
        if raw in ds.BASEMAPS:
            self.basemap = raw
            self._refresh_layers()

    def set_basemap_by_label(self, label: str):
        """Bridge for the select, which shows labels in the current language."""
        col = "label_pt" if self.language == "pt" else "label_en"
        lookup = {v[col]: k for k, v in ds.BASEMAPS.items()}
        key = lookup.get(label)
        if key:
            self.basemap = key
            self._refresh_layers()

    @rx.event(background=True)
    async def toggle_glc(self, checked: bool):
        async with self:
            self.show_glc = checked
            self._refresh_layers()
            lids = self._glc_lids(self.glc_year)
        if checked:
            for lid, g, y in lids:
                await self._mint(lid, lambda g=g, y=y: layer_service.glc_spec(y, g))

    @rx.event(background=True)
    async def set_glc_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.glc_year = int(raw)
            self._refresh_layers()
            lids, on = self._glc_lids(self.glc_year), self.show_glc
        if on:
            for lid, g, y in lids:
                await self._mint(lid, lambda g=g, y=y: layer_service.glc_spec(y, g))

    @rx.event(background=True)
    async def toggle_compare(self, checked: bool):
        """Swipe comparison of two years: turns the GLC layer on and mints both years."""
        async with self:
            self.compare_on = checked
            if checked:
                self.show_glc = True
            lids = self._glc_lids(self.glc_year) + self._glc_lids(self.compare_year)
            self._refresh_layers()
        if checked:
            for lid, g, y in lids:
                await self._mint(lid, lambda g=g, y=y: layer_service.glc_spec(y, g))

    @rx.event(background=True)
    async def set_compare_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.compare_year = int(raw)
            lids, on = self._glc_lids(self.compare_year), self.compare_on
            self._refresh_layers()
        if on:
            for lid, g, y in lids:
                await self._mint(lid, lambda g=g, y=y: layer_service.glc_spec(y, g))

    def set_glc_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.glc_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_loss_year(self, checked: bool):
        async with self:
            self.show_loss_year = checked
            self._refresh_layers()
        if checked:
            await self._mint("world:loss_year", layer_service.loss_year_spec)

    @rx.event(background=True)
    async def toggle_burn_year(self, checked: bool):
        async with self:
            self.show_burn_year = checked
            self._refresh_layers()
        if checked:
            await self._mint("world:burn_year", layer_service.burn_spec)

    @rx.event(background=True)
    async def toggle_treecover(self, checked: bool):
        async with self:
            self.show_treecover = checked
            self._refresh_layers()
            threshold = self.treecover_threshold
        if checked:
            await self._mint(f"world:hansen_tc:{threshold}",
                             lambda: layer_service.hansen_treecover_spec(threshold))

    def set_treecover_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.treecover_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_change(self, checked: bool):
        async with self:
            self.show_change = checked
            self._refresh_layers()
            yr, th = self.change_from_year, self.treecover_threshold
        if checked:
            await self._mint(f"world:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))

    @rx.event(background=True)
    async def set_change_from_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.change_from_year = int(raw)
            self._refresh_layers()
            yr, th, on = self.change_from_year, self.treecover_threshold, self.show_change
        if on:
            await self._mint(f"world:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))

    @rx.event(background=True)
    async def set_treecover_threshold(self, value: list[int | float]):
        """The forest definition. Governs both Hansen layers *and* the numbers
        in the change panel, which is why changing it re-runs the analysis."""
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.treecover_threshold = int(raw)
            self._refresh_layers()
            yr, th = self.change_from_year, self.treecover_threshold
            tc_on, ch_on = self.show_treecover, self.show_change
            lat, lon, has = self.study_lat, self.study_lon, self.has_point
        if tc_on:
            await self._mint(f"world:hansen_tc:{th}",
                             lambda: layer_service.hansen_treecover_spec(th))
        if ch_on:
            await self._mint(f"world:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))
        if has:
            return type(self).run_change_only(lat, lon)

    @rx.event(background=True)
    async def toggle_landsat(self, checked: bool):
        async with self:
            self.show_landsat = checked
            self._refresh_layers()
            key, yr = self.landsat_rendering, self.landsat_year
        if checked:
            await self._mint(f"world:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    @rx.event(background=True)
    async def set_landsat_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.landsat_year = int(raw)
            self._refresh_layers()
            key, yr, on = self.landsat_rendering, self.landsat_year, self.show_landsat
        if on:
            await self._mint(f"world:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    @rx.event(background=True)
    async def set_landsat_rendering(self, value: str | list[str]):
        raw = value[0] if isinstance(value, (list, tuple)) and value else value
        async with self:
            if raw in ds.LANDSAT_RENDERINGS:
                self.landsat_rendering = raw
            self._refresh_layers()
            key, yr, on = self.landsat_rendering, self.landsat_year, self.show_landsat
        if on:
            await self._mint(f"world:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    # ---------------------------------------------------------------------- #
    # Derived display values
    # ---------------------------------------------------------------------- #

    @rx.var
    def basemap_options(self) -> list[str]:
        col = "label_pt" if self.language == "pt" else "label_en"
        return [v[col] for v in ds.BASEMAPS.values()]

    @rx.var
    def basemap_label(self) -> str:
        col = "label_pt" if self.language == "pt" else "label_en"
        return ds.BASEMAPS[self.basemap][col]

    @rx.var
    def landsat_options(self) -> list[str]:
        col = "label_pt" if self.language == "pt" else "label_en"
        return [v[col] for v in ds.LANDSAT_RENDERINGS.values()]

    @rx.var
    def landsat_value(self) -> str:
        col = "label_pt" if self.language == "pt" else "label_en"
        return ds.LANDSAT_RENDERINGS[self.landsat_rendering][col]

    @rx.var
    def landsat_note(self) -> str:
        col = "note_pt" if self.language == "pt" else "note_en"
        return ds.LANDSAT_RENDERINGS[self.landsat_rendering][col]

    @rx.var
    def east_missing(self) -> bool:
        """The Asia and Australasia tile groups are not loaded yet (the page opens without them)."""
        return len(self.glc_groups) < len(layer_service.GROUPS)

    @rx.var
    def glc_opacity_pct(self) -> int:
        return int(round(self.glc_opacity * 100))

    @rx.var
    def treecover_opacity_pct(self) -> int:
        return int(round(self.treecover_opacity * 100))

    @rx.var
    def ee_status_label(self) -> str:
        if self.ee_error:
            return self.tr["status_ee_unavailable"]
        if not self.ee_ready:
            return self.tr["status_ee_connecting"]
        return self.tr["status_ee_ready"]
