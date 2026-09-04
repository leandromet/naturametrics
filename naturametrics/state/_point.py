"""Study-point state: where the user clicked, and whether it is usable.

Phase 0 establishes the click path end-to-end (map → Reflex event → validated
coordinate → UI). Phase 1 hangs buffers and the MapBiomas history off
``set_study_point``; nothing about the plumbing needs to change for that.
"""

from __future__ import annotations

import logging
from typing import Literal

import reflex as rx

from ..config.settings import (
    BUFFER_MODE_DEFAULT,
    BUFFER_RADII_KM,
    MAP_CLICK_ZOOM,
)
from ..services.buffers import buffer_geojson
from ..services.geo import CoordinateError, point, validate_for_analysis

logger = logging.getLogger(__name__)


class PointMixin(rx.State, mixin=True):
    """The location under analysis."""

    has_point: bool = False
    study_lat: float = 0.0
    study_lon: float = 0.0
    point_label: str = ""
    point_error: str = ""

    #: Where the point came from, and who it is. A map click is anonymous; a
    #: conglomerado is a named sampling location with a published identity, and
    #: an export that loses that distinction cannot be joined back to the IFN.
    point_source: str = "clique no mapa"
    point_conglomerado: str = ""
    point_uf: str = ""
    point_municipio: str = ""
    point_bioma: str = ""
    buffer_shape: Literal["circle", "square"] = "circle"

    def _clear_identity(self) -> None:
        self.point_source = "clique no mapa"
        self.point_conglomerado = ""
        self.point_uf = ""
        self.point_municipio = ""
        self.point_bioma = ""

    def set_study_point(self, lat: float, lon: float):
        """Handle a map click.

        The map hands us ``(lat, lon)`` in Leaflet's order. Everything downstream
        goes through :mod:`naturametrics.services.geo`, which is the only place
        allowed to reorder them — see that module for why.
        """
        if self.multi_mode:
            # Replacing the study point here would also replace the map's
            # overlays and the chart, quietly discarding a selection the user
            # spent real effort building. Refused, with the reason.
            self.point_error = self.tr["multi_blocked_point_error"]
            return

        # A region (drawn/pasted/uploaded, state/_geometry.py) is the same
        # kind of "current subject" a point is — a plain click replaces it,
        # same as it replaces a previously clicked point.
        if self.has_geometry:
            self.has_geometry = False
            self.geometry_error = ""
        # Belt and suspenders: the map's own click handler already refuses to
        # fire at all while draw_mode is armed (leaflet_map.js), but a click
        # reaching here regardless (e.g. a conglomerado clicked mid-draw)
        # should still leave the toolbar in a state that matches what just
        # happened, rather than staying armed and confusing.
        self.draw_mode = False

        # A bare map click carries no identity. Cleared here rather than in the
        # caller so that clicking away from a conglomerado cannot leave the
        # previous one's name attached to a different coordinate.
        self._clear_identity()
        try:
            p = point(lat=lat, lon=lon)
            validate_for_analysis(p, messages=self.tr)
        except CoordinateError as exc:
            self.has_point = False
            self.point_error = str(exc)
            self.point_label = ""
            logger.info("Rejected click at (%s, %s): %s", lat, lon, exc)
            return

        self.study_lat = p.lat
        self.study_lon = p.lon
        self.point_label = str(p)
        self.point_error = ""
        self.has_point = True
        self._open_study_area()
        logger.info("Study point set: %s", p)

        # Draw the rings immediately, from local geometry. Waiting on Earth
        # Engine to render a circle would make the app feel broken
        # (doc/07-ui-ux.md §2).
        self.buffer_overlays = buffer_geojson(
            p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, self.buffer_shape
        )
        # Show the land cover inside the largest buffer straight away — it needs
        # no Earth Engine call, so it lands well before the analysis does.
        self._set_preview(p.lat, p.lon)
        # Nudges the mobile sheet open toward "half" — never smaller — the
        # same map-app convention camposcope's equivalent selection paths
        # use. See pages/index.py::_SHEET_SCRIPT's window.__nmSheetSnapTo.
        return [type(self).run_analysis(p.lat, p.lon),
               rx.call_script(
                   "window.__nmSheetSnapTo && window.__nmSheetSnapTo('half')"),
               _zoom_to_click(p.lat, p.lon)]

    def clear_study_point(self):
        self.has_point = False
        self.point_label = ""
        self.point_error = ""
        self.buffer_overlays = {}
        self.has_result = False
        self._clear_identity()
        self._clear_preview()

    def toggle_buffer_shape(self, checked: bool):
        self.buffer_shape = "square" if checked else "circle"
        # selected_age_radius is a stored label, not a float — it must be reset
        # here or it keeps the old shape's suffix and no longer matches any
        # current age_tab_options entry (unlike selected_radius, whose label is
        # derived fresh from buffer_shape on every render). Mirrors the same
        # "Ponto" vs multi-sum condition age_tab_options uses, so the reset
        # value is always one of the options actually on offer.
        self.selected_age_radius = (
            self._radius_label(BUFFER_RADII_KM[0])
            if (self.multi_mode and self._multi_age_history) else "Ponto"
        )
        # A cached full-area bounding box was built from the old shape's
        # buffers — no longer describes the current selection.
        self.multi_bbox_stale = True
        if self.multi_mode:
            self.multi_error = self.tr["multi_shape_change_note"]
            return
        if self.has_point:
            from ..services.geo import point
            p = point(lat=self.study_lat, lon=self.study_lon)
            self.buffer_overlays = buffer_geojson(
                p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT, self.buffer_shape)
            self._set_preview(p.lat, p.lon)
            return type(self).run_analysis(p.lat, p.lon)

    @rx.var
    def point_identity_label(self) -> str:
        """"MT_1913 · Cuiabá/MT" for a conglomerado, empty for a map click."""
        if not self.point_conglomerado:
            return ""
        place = " · ".join(x for x in (self.point_municipio, self.point_uf) if x)
        return f"{self.point_conglomerado} — {place}" if place else self.point_conglomerado


def _zoom_to_click(lat: float, lon: float):
    """Centre the map on a freshly clicked point, zooming in to
    ``MAP_CLICK_ZOOM`` if it is currently wider than that.

    Driven from the browser rather than through the ``map_center``/``map_zoom``
    state vars this component also honours, for one reason: those vars record
    what Python last *asked* for, and nothing writes the user's own panning and
    zooming back into them (``components/map/leaflet_map.js`` deliberately
    binds ``moveend``/``zoomend`` only to refetch dynamic layers). Setting
    ``map_zoom = 8`` from here would therefore zoom a user who had worked their
    way down to a single field back OUT to 8 the moment they clicked. Only the
    live Leaflet instance knows the real answer, and it is already exposed for
    exactly this kind of imperative fly-to: ``leaflet_map.js`` hangs the map on
    its own container node as ``_nmMap`` (see the comment there), and the
    container carries the literal ``id`` ``LeafletMap`` requires.

    Both pages' maps are looked up, not just the Brazil one, so the Canada page
    (``nm-canada-map``) gets the same behaviour from its own click handler
    without a second copy of this.
    """
    return rx.call_script(
        "(function () {"
        "  var ids = ['nm-map', 'nm-canada-map'];"
        "  for (var i = 0; i < ids.length; i++) {"
        "    var el = document.getElementById(ids[i]);"
        "    var map = el && el._nmMap;"
        "    if (!map) continue;"
        f"    var target = Math.max(map.getZoom(), {MAP_CLICK_ZOOM});"
        f"    map.setView([{lat}, {lon}], target, {{animate: true}});"
        "  }"
        "})()"
    )
