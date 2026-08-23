"""A user-supplied study region: drawn on the map, pasted as WKT, or uploaded
as a KML file.

A region **replaces** the current subject of analysis exactly the way
``PointMixin.set_study_point`` does — it is not summed with anything the way
multi-selection is — so it writes through the *same* result-storage fields
``AnalysisMixin`` already has (``_history``, ``_age_buffers``,
``_landscape_metrics``, ``_biomass``, ``_veg_compare`` and their provenances,
``has_result``, ``point_label``, ``buffer_overlays``). Every existing display
component (results panel, charts, the study-point export) already reads those
fields and needs no change to show a region's results — only the handful of
"is there a radius to pick" gates in state/_analysis.py need a
``geometry_active`` branch alongside the ``full_area_active`` one they already
have.

See ``services/region_geometry.py`` for why this is architecturally cheap: it
is the same single-feature ``ee.FeatureCollection`` shape multi-selection's
"área total" mode already established for a bounding box, with an exact
polygon in that slot instead.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import reflex as rx

from ..services.biomass import region_biomass_history
from ..services.ibge_vegetation import region_mapbiomas_comparison
from ..services.landscape_metrics import region_landscape_metrics
from ..services.mapbiomas_history import region_land_cover_history
from ..services.region_geometry import (
    GeometryError, area_ha as geometry_area_ha, parse_kml_polygons, parse_wkt,
    polygon_from_geojson, region_geojson, validate_region,
)
from ..services.vegetation_age import region_forest_age_histogram

logger = logging.getLogger(__name__)


class GeometryMixin(rx.State, mixin=True):
    """The drawn/uploaded study region."""

    has_geometry: bool = False
    geometry_error: str = ""
    #: The region's true geodesic area — set alongside point_label, read
    #: separately by region_mode_label (state/_analysis.py) for the badge
    #: that replaces the radius selector while a region is active.
    geometry_area_ha: float = 0.0

    #: Arms the on-map draw toolbar. Off by default so its buttons do not
    #: appear — and, more importantly, so a plain map click keeps picking a
    #: point — until the user asks for drawing specifically. Without this a
    #: click that FINISHES a shape (mouseup on a rectangle's second corner,
    #: or the closing click of a polygon) also reaches the map's own click
    #: handler and gets read as "pick a point here", which is what happened
    #: before this switch existed.
    draw_mode: bool = False

    #: Paste-WKT tab of the "Enviar dados" panel.
    wkt_text: str = ""

    def toggle_draw_mode(self, checked: bool):
        """Same exclusivity rule as toggle_multi_mode: only one "what does a
        click/drag on the map mean right now" mode at a time."""
        self.draw_mode = checked
        self.geometry_error = ""
        if checked and self.multi_mode:
            self.toggle_multi_mode(False)
        if checked and self.user_points_active:
            self.user_points_active = False
            self._refresh_layers()

    def _clear_other_subjects(self) -> None:
        """Only one subject drives the map/results at a time — same rule
        ``submit_user_points``/``toggle_multi_mode`` already enforce between
        each other."""
        if self.multi_mode:
            self.toggle_multi_mode(False)
        if self.user_points_active:
            self.user_points_active = False
            self._refresh_layers()
        self.clear_study_point()

    def _apply_geometry(self, geom: Any, label: str, source: str) -> Any:
        """Validate, draw, and kick off the analysis. ``source`` is the
        already-translated string shown as the region's provenance origin
        ("desenho no mapa" / "WKT colado" / "arquivo KML")."""
        try:
            geom = validate_region(geom, messages=self.tr)
        except GeometryError as exc:
            self.geometry_error = str(exc)
            return

        self._clear_other_subjects()
        self.geometry_error = ""
        self.has_geometry = True
        self.geometry_area_ha = geometry_area_ha(geom)
        self.point_label = f"{label} — {self.geometry_extent_label}"
        self.point_source = source
        # Not a real study point, but download_study_point (state/_export.py)
        # still needs *some* coordinate for the workbook's identity row and
        # filename — the centroid is the least surprising choice, and reuses
        # study_lat/study_lon rather than adding a parallel pair of fields.
        centroid = geom.centroid
        self.study_lat, self.study_lon = centroid.y, centroid.x
        self.buffer_overlays = region_geojson(geom, label)
        # A bare geometry dict, not the FeatureCollection above — this is the
        # value that crosses the reactive boundary into the background event,
        # which reconstructs the shapely geometry from it (state may not hold
        # shapely/ee objects, only plain JSON-safe values).
        from shapely.geometry import mapping

        return type(self).run_geometry_analysis(mapping(geom), label)

    def on_geometry_drawn(self, geojson: dict | None):
        """Wired to the map's ``on_geometry_drawn`` — fired with a GeoJSON
        Feature when the draw toolbar finishes a polygon/rectangle. The
        toolbar has no edit/remove tool of its own (nothing persists in its
        own layer group to edit — the region is drawn from the server echo
        in ``buffer_overlays``, same channel WKT/KML use); clearing goes
        through the sidebar's "Limpar" button (``clear_geometry``) instead.
        ``None`` is accepted defensively for the same reason ``clear_geometry``
        is idempotent — a future clear-from-the-map affordance can reuse this
        handler without a Python-side change.

        Disarms ``draw_mode`` on success — one shape is what "draw a region"
        means (replaced, not accumulated, same as everywhere else a subject
        is chosen), so the toolbar and its click-suppression only need to
        stay armed for exactly the gesture that produces it.
        """
        if not geojson:
            self.clear_geometry()
            return
        try:
            geom = polygon_from_geojson(geojson)
        except GeometryError as exc:
            self.geometry_error = str(exc)
            return
        self.draw_mode = False
        return self._apply_geometry(geom, self.tr["geometry_label_drawn"],
                                      self.tr["geometry_source_drawn"])

    def set_wkt_text(self, value: str):
        self.wkt_text = value

    def submit_wkt(self):
        try:
            geom = parse_wkt(self.wkt_text, messages=self.tr)
        except GeometryError as exc:
            self.geometry_error = str(exc)
            return
        return self._apply_geometry(geom, self.tr["geometry_label_wkt"],
                                      self.tr["geometry_source_wkt"])

    @rx.event
    async def handle_kml_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        data = await files[0].read()
        try:
            geom = parse_kml_polygons(data, messages=self.tr)
        except GeometryError as exc:
            self.geometry_error = str(exc)
            return
        return self._apply_geometry(geom, self.tr["geometry_label_kml"],
                                      self.tr["geometry_source_kml"])

    def clear_geometry(self):
        self.has_geometry = False
        self.geometry_error = ""
        self.has_result = False
        self.point_label = ""
        self.buffer_overlays = {}
        self._clear_identity()
        self._clear_preview()

    @rx.event(background=True)
    async def run_geometry_analysis(self, geojson: dict, label: str):
        """Compute every product for a freshly confirmed region — same
        gather/try-except/token-guard shape as
        ``AnalysisMixin.run_analysis``, sharing its ``_run_token`` so a
        region and a point click can never race each other's result into the
        same fields.
        """
        async with self:
            self._run_token += 1
            token = self._run_token
            self.analysis_running = True
            self.analysis_error = ""
            self.has_result = False
            self.landscape_metrics_running = True
            self.landscape_metrics_error = ""
            self._landscape_metrics = []
            self._landscape_metrics_provenance = {}
            self.biomass_running = True
            self.biomass_error = ""
            self._biomass = []
            self._biomass_provenance = {}
            self.veg_compare_running = True
            self.veg_compare_error = ""
            self._veg_compare = []
            self._veg_compare_provenance = {}
            # No 30 m single-pixel/point series exists for a region — cleared
            # rather than left stale from whatever point was selected before.
            self._pixel = []
            self._pixel_provenance = {}
            self.age_running = True
            self.age_error = ""
            self._age_point = []
            self._age_point_provenance = {}
            self._change_stats = {}
            self._change_provenance = {}

        geom = polygon_from_geojson(geojson)
        loop = asyncio.get_running_loop()

        history_task = loop.run_in_executor(None, region_land_cover_history, geom, label)
        age_task = loop.run_in_executor(None, region_forest_age_histogram, geom, label)
        metrics_task = loop.run_in_executor(None, region_landscape_metrics, geom, label)
        biomass_task = loop.run_in_executor(None, region_biomass_history, geom, label)
        veg_compare_task = loop.run_in_executor(
            None, region_mapbiomas_comparison, geom, label)

        try:
            df, prov = await history_task
        except Exception as exc:  # noqa: BLE001
            logger.exception("Region analysis failed")
            async with self:
                if token == self._run_token:
                    self.analysis_running = False
                    self.analysis_error = self.tr["err_earth_engine_query"].format(exc=exc)
            return

        async with self:
            if token != self._run_token:
                logger.info("Discarding superseded region analysis for %s", label)
                return
            self._history = df.to_dict("records")
            self._provenance = prov.to_dict()
            self.analysis_running = False
            self.has_result = not df.empty
            if df.empty:
                self.analysis_error = self.tr["err_no_landcover"]

        try:
            age_df, age_prov = await age_task
        except Exception as exc:  # noqa: BLE001
            logger.exception("Region forest-age analysis failed")
            async with self:
                if token == self._run_token:
                    self.age_running = False
                    self.age_error = self.tr["err_vegetation_age_failed"].format(exc=exc)
        else:
            async with self:
                if token == self._run_token:
                    self._age_buffers = age_df.to_dict("records")
                    self._age_buffers_provenance = age_prov.to_dict()
                    self.age_running = False
                    if age_df.empty:
                        self.age_error = self.tr["err_no_vegetation_age"]

        try:
            metrics_df, _hist_df, metrics_prov = await metrics_task
        except Exception as exc:  # noqa: BLE001
            logger.exception("Region landscape metrics failed")
            async with self:
                if token == self._run_token:
                    self.landscape_metrics_running = False
                    self.landscape_metrics_error = \
                        self.tr["err_landscape_metrics_failed"].format(exc=exc)
        else:
            async with self:
                if token == self._run_token:
                    self._landscape_metrics = metrics_df.to_dict("records")
                    self._landscape_metrics_provenance = metrics_prov.to_dict()
                    self.landscape_metrics_running = False

        try:
            biomass_df, biomass_prov = await biomass_task
        except Exception as exc:  # noqa: BLE001
            logger.exception("Region biomass failed")
            async with self:
                if token == self._run_token:
                    self.biomass_running = False
                    self.biomass_error = self.tr["err_biomass_failed"].format(exc=exc)
        else:
            async with self:
                if token == self._run_token:
                    self._biomass = biomass_df.to_dict("records")
                    self._biomass_provenance = biomass_prov.to_dict()
                    self.biomass_running = False

        try:
            veg_compare_df, veg_compare_prov = await veg_compare_task
        except Exception as exc:  # noqa: BLE001
            logger.exception("Region IBGE vegetation comparison failed")
            async with self:
                if token == self._run_token:
                    self.veg_compare_running = False
                    self.veg_compare_error = self.tr["err_ibge_veg_failed"].format(exc=exc)
        else:
            async with self:
                if token == self._run_token:
                    self._veg_compare = veg_compare_df.to_dict("records")
                    self._veg_compare_provenance = veg_compare_prov.to_dict()
                    self.veg_compare_running = False

    # --- derived ------------------------------------------------------- #

    @rx.var
    def has_subject(self) -> bool:
        """A point or a region is under analysis — the OR every visibility
        gate that used to read ``has_point`` alone now needs."""
        return self.has_point or self.has_geometry

    @rx.var(cache=True)
    def geometry_active(self) -> bool:
        return self.has_geometry

    @rx.var(cache=True)
    def geometry_extent_label(self) -> str:
        pt = self.language == "pt"
        text = f"{self.geometry_area_ha:,.0f} ha"
        return text.replace(",", ".") if pt else text
