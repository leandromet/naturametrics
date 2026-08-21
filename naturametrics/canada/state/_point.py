"""Study-point state for the Canada page.

Mirrors the Brazil page's point handling, with the one Canadian difference that
drives the whole design: a click north of the AAFC extent is **valid**. It sets
the point, draws the buffers and runs the analysis; only the land-cover panel
comes back empty, and it says why. See ``canada/services/geo.py``.
"""

from __future__ import annotations

import logging

import reflex as rx

from ...config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
from ...services.buffers import buffer_geojson
from ..services.geo import CoordinateError, north_of_aci, point, validate_for_analysis

logger = logging.getLogger(__name__)


class CanadaPointMixin(rx.State, mixin=True):
    """The location under analysis."""

    has_point: bool = False
    study_lat: float = 0.0
    study_lon: float = 0.0
    point_label: str = ""
    point_error: str = ""

    #: Whether the crop inventory is expected to have nothing here. Held in state
    #: rather than recomputed in the component so the warning appears with the
    #: click, not after the Earth Engine round-trip returns an empty frame.
    point_north_of_aci: bool = False

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
            logger.info("Rejected Canada click at (%s, %s): %s", lat, lon, exc)
            return

        self.study_lat = p.lat
        self.study_lon = p.lon
        self.point_label = str(p)
        self.point_error = ""
        self.has_point = True
        self.point_north_of_aci = north_of_aci(p)
        logger.info("Canada study point set: %s (north_of_aci=%s)",
                    p, self.point_north_of_aci)

        # Rings drawn immediately from local geometry — waiting on Earth Engine
        # to draw a circle would make the app feel broken.
        self.buffer_overlays = buffer_geojson(p, BUFFER_RADII_KM, BUFFER_MODE_DEFAULT)
        # Same immediacy for the magnifier: its tile URL was warmed at startup
        # and the clip is applied in the browser, so it lands with the click
        # rather than after the analysis returns.
        self._set_preview(p.lat, p.lon)
        return type(self).run_analysis(p.lat, p.lon)

    def clear_study_point(self):
        self.has_point = False
        self.point_label = ""
        self.point_error = ""
        self.point_north_of_aci = False
        self.buffer_overlays = {}
        self.has_result = False
        self._clear_preview()
