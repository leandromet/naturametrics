"""Study-point state: where the user clicked, and whether it is usable.

Phase 0 establishes the click path end-to-end (map → Reflex event → validated
coordinate → UI). Phase 1 hangs buffers and the MapBiomas history off
``set_study_point``; nothing about the plumbing needs to change for that.
"""

from __future__ import annotations

import logging
from typing import Literal

import reflex as rx

from ..config.settings import BUFFER_MODE_DEFAULT, BUFFER_RADII_KM
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
        return type(self).run_analysis(p.lat, p.lon)

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
