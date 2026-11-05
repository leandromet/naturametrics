"""Study-point state for the USA page.

Mirrors the Brazil page's point handling. A click must fall inside the lower 48
(box plus LSIB, see ``usa/services/geo.py``); anything else is refused with a message.
"""

from __future__ import annotations

import logging

import reflex as rx

from ...config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
from ...services.buffers import buffer_geojson
from ...state._point import _zoom_to_click
from ..services.geo import CoordinateError, point, region_of, validate_for_analysis

logger = logging.getLogger(__name__)


class USPointMixin(rx.State, mixin=True):
    """The location under analysis."""

    has_point: bool = False
    study_lat: float = 0.0
    study_lon: float = 0.0
    point_label: str = ""
    point_error: str = ""

    def set_study_point(self, lat: float, lon: float):
        """Handle a map click.

        The map hands us ``(lat, lon)`` in Leaflet's order; everything
        downstream goes through the shared geo module, which is the only place
        allowed to reorder them.
        """
        try:
            p = point(lat=lat, lon=lon)
            validate_for_analysis(p, messages=self.tr)
        except CoordinateError as exc:
            self.has_point = False
            self.point_error = str(exc)
            self.point_label = ""
            logger.info("Rejected USA click at (%s, %s): %s", lat, lon, exc)
            return

        self.study_lat = p.lat
        self.study_lon = p.lon
        self.point_label = str(p)
        self.point_error = ""
        self.has_point = True
        logger.info("USA study point set: %s", p)

        # Rings drawn immediately from local geometry — waiting on Earth Engine
        # to draw a circle would make the app feel broken.
        self.buffer_overlays = buffer_geojson(p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
        # Same immediacy for the magnifier: its tile URL was warmed at startup
        # and the clip is applied in the browser, so it lands with the click
        # rather than after the analysis returns.
        self._set_preview(p.lat, p.lon)
        # Same click-zoom as the Brazil page — the helper looks both maps up
        # by id, so there is nothing US-specific to duplicate here.
        return [type(self).warm_layer_region(region_of(p) or "conus"),
                type(self).run_analysis(p.lat, p.lon),
                type(self).run_landscape_biomass(p.lat, p.lon),
                type(self).run_extras(p.lat, p.lon),
                _zoom_to_click(p.lat, p.lon)]

    def clear_study_point(self):
        self.has_point = False
        self.point_label = ""
        self.point_error = ""
        self.buffer_overlays = {}
        self.has_result = False
        self._clear_preview()
