"""Map layer state for the USA page.

Same shape as the Brazil page's layer state and for the same reason: the layer
list is plain state rather than a computed var, because building it can require
minting Earth Engine tile URLs and a computed var would re-run that on every
read.

Three toggleable Earth Engine layers, each independent: the Annual NLCD classification
for one year, Hansen tree cover, and the Hansen loss/gain mask —
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
from ..config import nlcd
from ..config import datasets as ds
from ..config import forest as fc_cfg
from ..config import settings as ca_st
from ..services import gbif as gbif_service
from ..services import layers as layer_service

logger = logging.getLogger(__name__)


class USLayersMixin(rx.State, mixin=True):
    """Which layers are on the map, and what the map is showing."""

    # --- view -------------------------------------------------------------
    map_center: list[float] = [ca_st.MAP_CENTER[0], ca_st.MAP_CENTER[1]]
    map_zoom: int = ca_st.MAP_ZOOM
    map_bounds: list[list[float]] = [list(ca_st.USA_VIEW_BOUNDS[0]),
                                     list(ca_st.USA_VIEW_BOUNDS[1])]
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

    # --- NLCD --------------------------------------------------------------
    show_nlcd: bool = False
    #: Region of the current study point (``conus`` | ``ak`` | ``hi``): Alaska has three NLCD
    #: snapshot years and Hawaii no land cover, so the layer ids and the preview depend on it.
    layer_region: str = "conus"
    nlcd_year: int = nlcd.NLCD_YEAR_END
    nlcd_opacity: float = 0.75
    #: Swipe comparison of two NLCD years: the baseline (``compare_year``, default the oldest the
    #: region has) on the left of the divider, the active ``nlcd_year`` (default the newest) on the right.
    compare_on: bool = False
    compare_year: int = nlcd.NLCD_YEAR_START

    # --- buffer preview ("magnifying glass") ------------------------------
    #: Shows the crop inventory *only inside* the analysis radius around the
    #: clicked point, and nowhere else. Costs no Earth Engine call: the tile URL
    #: is minted once at startup and the restriction to a circle is a CSS clip
    #: applied in the browser (see leaflet_map.js).
    #:
    #: Always the **most recent** NLCD year rather than whatever the year slider
    #: happens to be on — the magnifier answers "what is here now", and pairing
    #: it with a slider the user moved for a different purpose would make it
    #: quietly disagree with itself.
    show_buffer_preview: bool = True
    preview_points: list[list[float]] = []

    # --- canopy, disturbance, fire (USFS TCC, LCMS, MTBS) ------------------
    show_tcc: bool = False
    tcc_year: int = 2025
    show_lcms: bool = False
    show_mtbs: bool = False

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

    def _nlcd_lid(self, year: int) -> tuple[str, int]:
        """Layer id and the year actually drawn (snapped to what the region has)."""
        y = nlcd.nearest_year(self.layer_region, year)
        return (f"us:nlcd:{y}" if self.layer_region == "conus" else f"us:nlcd:{self.layer_region}:{y}"), y

    def _cached_specs(self):
        """Yield (id, spec) for every enabled Earth Engine layer.

        Reads only ``_url_cache``; nothing here mints. Minting happens in the
        background events below, which then call ``_refresh_layers``.
        """
        if self.show_landsat:
            lid = f"us:landsat:{self.landsat_rendering}:{self.landsat_year}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": 1.0,
                    "attribution": f"{ds.LANDSAT_ATTRIBUTION} — {self.landsat_year}",
                    "z_index": 1, "max_native_zoom": 14,
                }

        if self.show_nlcd and self.layer_region not in nlcd.NO_LANDCOVER:
            lid, drawn = self._nlcd_lid(self.nlcd_year)
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": self.nlcd_opacity,
                    "attribution": f"{layer_service.NLCD_ATTRIBUTION} {drawn}",
                    "z_index": 10, "max_native_zoom": 15,
                    "clip": "right" if self.compare_on else None,
                }
            if self.compare_on:
                lid_b, drawn_b = self._nlcd_lid(self.compare_year)
                url_b = self._url_cache.get(lid_b)
                if url_b:
                    yield f"{lid_b}:cmp", {
                        "id": f"{lid_b}:cmp", "url": url_b, "opacity": self.nlcd_opacity,
                        "attribution": f"{layer_service.NLCD_ATTRIBUTION} {drawn_b}",
                        "z_index": 11, "max_native_zoom": 15, "clip": "left",
                    }

        # Suppressed while the full NLCD layer is on — the coverage is already
        # painted across the whole map, so a magnifier over it shows nothing new.
        if (self.show_buffer_preview and self.preview_points and not self.show_nlcd
                and self.layer_region not in nlcd.NO_LANDCOVER):
            lid, drawn = self._nlcd_lid(nlcd.NLCD_YEAR_END)
            url = self._url_cache.get(lid)
            if url:
                yield f"us:preview:{lid}", {
                    "id": f"us:preview:{lid}",
                    "url": url,
                    "opacity": BUFFER_PREVIEW_OPACITY,
                    "attribution": f"{layer_service.NLCD_ATTRIBUTION} {drawn}",
                    "z_index": 13, "max_native_zoom": 15,
                    "clip_circles": [{"lat": lat, "lon": lon}
                                     for lat, lon in self.preview_points],
                    "clip_radius_km": BUFFER_PREVIEW_RADIUS_KM,
                    "clip_shape": BUFFER_PREVIEW_SHAPE,
                }

        if self.show_tcc:
            lid = f"us:tcc:{self.layer_region}:{self.tcc_year}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {"id": lid, "url": url, "opacity": 0.7,
                            "attribution": f"USFS GTAC — NLCD Tree Canopy Cover {self.tcc_year}",
                            "z_index": 11, "max_native_zoom": 15}
        if self.show_lcms:
            lid = f"us:lcms_loss:{self.layer_region}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {"id": lid, "url": url, "opacity": 0.8,
                            "attribution": "USFS GTAC — LCMS v2025-11: most recent disturbance year",
                            "z_index": 12, "max_native_zoom": 15}
        if self.show_mtbs:
            lid = f"us:mtbs:{self.layer_region}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {"id": lid, "url": url, "opacity": 0.8,
                            "attribution": "USGS/USFS — MTBS burn severity (highest on record)",
                            "z_index": 13, "max_native_zoom": 15}

        if self.show_treecover:
            lid = f"us:hansen_tc:{self.treecover_threshold}"
            url = self._url_cache.get(lid)
            if url:
                yield lid, {
                    "id": lid, "url": url, "opacity": self.treecover_opacity,
                    "attribution": layer_service.HANSEN_ATTRIBUTION,
                    "z_index": 11, "max_native_zoom": 15,
                }

        if self.show_change:
            lid = f"us:hansen_change:{self.change_from_year}:{self.treecover_threshold}"
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
            # (USGbifMixin.on_gbif_layer_meta) — same reasoning as the
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
        await self._mint(f"us:nlcd:{nlcd.NLCD_YEAR_END}",
                         lambda: layer_service.nlcd_spec(nlcd.NLCD_YEAR_END))

    @rx.event(background=True)
    async def warm_layer_region(self, region: str):
        """Switch the NLCD layer family to the clicked point's region and mint the magnifier's tile."""
        async with self:
            self.layer_region = region
            years = nlcd.years_for(region)
            if years:                       # oldest vs newest the region has, as the defaults
                self.compare_year, self.nlcd_year = years[0], years[-1]
            self._refresh_layers()
            lid, year = self._nlcd_lid(nlcd.NLCD_YEAR_END)
            tcc_on, tcc_year, lcms_on, mtbs_on = self.show_tcc, self.tcc_year, self.show_lcms, self.show_mtbs
            cmp_on = self.compare_on
            lid_cmp, year_cmp = self._nlcd_lid(self.compare_year)
        if region not in nlcd.NO_LANDCOVER:
            await self._mint(lid, lambda: layer_service.nlcd_spec(year, region=region))
        if cmp_on and region not in nlcd.NO_LANDCOVER:
            await self._mint(lid_cmp, lambda: layer_service.nlcd_spec(year_cmp, region=region))
        if tcc_on:
            await self._mint(f"us:tcc:{region}:{tcc_year}", lambda: layer_service.tcc_spec(tcc_year, region))
        if lcms_on:
            await self._mint(f"us:lcms_loss:{region}", lambda: layer_service.lcms_loss_spec(region))
        if mtbs_on:
            await self._mint(f"us:mtbs:{region}", lambda: layer_service.mtbs_spec(region))

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
    async def toggle_nlcd(self, checked: bool):
        async with self:
            self.show_nlcd = checked
            self._refresh_layers()
            year = self.nlcd_year
        if checked:
            await self._mint(f"us:nlcd:{year}",
                             lambda: layer_service.nlcd_spec(year))

    @rx.event(background=True)
    async def set_nlcd_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.nlcd_year = int(raw)
            self._refresh_layers()
            year, on = self.nlcd_year, self.show_nlcd
        if on:
            await self._mint(f"us:nlcd:{year}",
                             lambda: layer_service.nlcd_spec(year))

    @rx.event(background=True)
    async def toggle_compare(self, checked: bool):
        """Swipe comparison of two years: turns the NLCD layer on and mints both years."""
        async with self:
            self.compare_on = checked
            if checked:
                self.show_nlcd = True
            region = self.layer_region
            lid_a, year_a = self._nlcd_lid(self.nlcd_year)
            lid_b, year_b = self._nlcd_lid(self.compare_year)
            self._refresh_layers()
        if checked and region not in nlcd.NO_LANDCOVER:
            await self._mint(lid_a, lambda: layer_service.nlcd_spec(year_a, region=region))
            await self._mint(lid_b, lambda: layer_service.nlcd_spec(year_b, region=region))

    @rx.event(background=True)
    async def set_compare_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.compare_year = int(raw)
            lid, year = self._nlcd_lid(self.compare_year)
            on, region = self.compare_on, self.layer_region
            self._refresh_layers()
        if on and region not in nlcd.NO_LANDCOVER:
            await self._mint(lid, lambda: layer_service.nlcd_spec(year, region=region))

    def set_nlcd_opacity(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        self.nlcd_opacity = round(float(raw) / 100.0, 2)
        self._refresh_layers()

    @rx.event(background=True)
    async def toggle_tcc(self, checked: bool):
        async with self:
            self.show_tcc = checked
            region, year = self.layer_region, self.tcc_year
            self._refresh_layers()
        if checked:
            await self._mint(f"us:tcc:{region}:{year}", lambda: layer_service.tcc_spec(year, region))

    @rx.event(background=True)
    async def set_tcc_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.tcc_year = int(raw)
            region, year, on = self.layer_region, self.tcc_year, self.show_tcc
            self._refresh_layers()
        if on:
            await self._mint(f"us:tcc:{region}:{year}", lambda: layer_service.tcc_spec(year, region))

    @rx.event(background=True)
    async def toggle_lcms(self, checked: bool):
        async with self:
            self.show_lcms = checked
            region = self.layer_region
            self._refresh_layers()
        if checked:
            await self._mint(f"us:lcms_loss:{region}", lambda: layer_service.lcms_loss_spec(region))

    @rx.event(background=True)
    async def toggle_mtbs(self, checked: bool):
        async with self:
            self.show_mtbs = checked
            region = self.layer_region
            self._refresh_layers()
        if checked:
            await self._mint(f"us:mtbs:{region}", lambda: layer_service.mtbs_spec(region))

    @rx.event(background=True)
    async def toggle_treecover(self, checked: bool):
        async with self:
            self.show_treecover = checked
            self._refresh_layers()
            threshold = self.treecover_threshold
        if checked:
            await self._mint(f"us:hansen_tc:{threshold}",
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
            await self._mint(f"us:hansen_change:{yr}:{th}",
                             lambda: layer_service.hansen_change_spec(yr, th))

    @rx.event(background=True)
    async def set_change_from_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.change_from_year = int(raw)
            self._refresh_layers()
            yr, th, on = self.change_from_year, self.treecover_threshold, self.show_change
        if on:
            await self._mint(f"us:hansen_change:{yr}:{th}",
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
            await self._mint(f"us:hansen_tc:{th}",
                             lambda: layer_service.hansen_treecover_spec(th))
        if ch_on:
            await self._mint(f"us:hansen_change:{yr}:{th}",
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
            await self._mint(f"us:landsat:{key}:{yr}",
                             lambda: layer_service.landsat_spec(key, yr))

    @rx.event(background=True)
    async def set_landsat_year(self, value: list[int | float]):
        raw = value[0] if isinstance(value, (list, tuple)) else value
        async with self:
            self.landsat_year = int(raw)
            self._refresh_layers()
            key, yr, on = self.landsat_rendering, self.landsat_year, self.show_landsat
        if on:
            await self._mint(f"us:landsat:{key}:{yr}",
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
            await self._mint(f"us:landsat:{key}:{yr}",
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
    def nlcd_opacity_pct(self) -> int:
        return int(round(self.nlcd_opacity * 100))

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
