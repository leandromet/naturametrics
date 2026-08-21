"""A pasted coordinate list, standing in for the IFN conglomerado grid.

**Only one list at a time.** Submitting a new paste replaces whatever was there
before, rather than merging — the export and the map layer would otherwise have
to explain "which submission is this row from", which is a question nobody asked.
"Reset" is the explicit, named way to get back to nothing, distinct from just
submitting an empty paste (which the parser would report as zero points and leave
the previous list untouched, since there is nothing to replace it *with*).

See services/user_points.py for the parser and why paste-only (no file upload).
"""

from __future__ import annotations

from typing import Any

import reflex as rx

from ..config.settings import USER_POINTS_MAX_LINES
from ..services.user_points import EXAMPLE_TEXT, parse_coordinate_text


class UserPointsMixin(rx.State, mixin=True):
    """The "Enviar dados" panel and the layer it drives."""

    user_points_dialog_open: bool = False
    user_points_text: str = ""
    #: [{"id", "lat", "lon"}, ...] — the parsed, kept points (up to the cap).
    user_points: list[dict[str, Any]] = []
    #: Human-readable parse problems: unparseable lines, out-of-range or
    #: out-of-Brazil coordinates, the truncation notice. Shown, never hidden —
    #: a coordinate list silently dropping a row is worse than one that says so.
    user_points_errors: list[str] = []
    #: Whether the list currently governs map hover/click instead of the IFN
    #: conglomerados. Distinct from "is the list empty": turning this off does
    #: not discard the list (see toggle in components), only submitting a new
    #: one or pressing "Reset" does.
    user_points_active: bool = False

    #: Bumped on every submit/reset so the map layer's id changes — the browser
    #: hook treats a vector layer's geometry as immutable once built (only
    #: opacity may change), matching every OTHER static layer in the app, so a
    #: replaced point set has to be a *new* id rather than a mutation of the old
    #: one. See leaflet_map.js, the static-vector sync effect.
    _user_points_version: int = 0

    def set_user_points_text(self, value: str):
        self.user_points_text = value

    def set_user_points_dialog_open(self, value: bool):
        self.user_points_dialog_open = value
        if value:
            self.user_points_errors = []

    def submit_user_points(self):
        """Parse the pasted text and make it the active layer.

        Pure string parsing, no Earth Engine call — plain event, not background.
        """
        result = parse_coordinate_text(self.user_points_text)
        self.user_points = result.points
        self.user_points_errors = list(result.errors)
        if result.truncated:
            self.user_points_errors.insert(
                0, self.tr["send_truncated"].format(max=USER_POINTS_MAX_LINES)
            )
        self._user_points_version += 1

        if not self.user_points:
            # Nothing parsed: leave whatever was active alone (there is nothing
            # to replace it with) and keep the dialog open so the errors are
            # visible next to the text that produced them.
            self.user_points_active = False
            return

        # Only one point-source mode at a time: a running multi-selection was
        # built by clicking conglomerados, which stop being the clickable layer
        # the moment this one takes over. The selection itself is not cleared —
        # same reasoning as toggle_multi_mode's own off-switch — only the mode.
        if self.multi_mode:
            self.toggle_multi_mode(False)
        self.user_points_active = True
        self.user_points_dialog_open = False
        self.clear_study_point()
        self._refresh_layers()

    def reset_user_points(self):
        """Remove the current coordinates and clear whatever they produced."""
        self.user_points = []
        self.user_points_errors = []
        self.user_points_text = ""
        self.user_points_active = False
        self._user_points_version += 1
        self.clear_study_point()
        self._refresh_layers()

    # ---------------------------------------------------------------------- #
    # Derived
    # ---------------------------------------------------------------------- #

    @rx.var(cache=True)
    def user_points_count(self) -> int:
        return len(self.user_points)

    @rx.var(cache=True)
    def user_points_max(self) -> int:
        return USER_POINTS_MAX_LINES

    @rx.var(cache=True)
    def user_points_max_label(self) -> str:
        return self.tr["send_max_points"].format(max=USER_POINTS_MAX_LINES)

    @rx.var(cache=True)
    def user_points_active_label(self) -> str:
        return self.tr["send_active_points"].format(n=self.user_points_count)

    @rx.var(cache=True)
    def user_points_example(self) -> str:
        return EXAMPLE_TEXT

    @rx.var(cache=True)
    def user_points_has_errors(self) -> bool:
        return bool(self.user_points_errors)

    @rx.var(cache=True)
    def user_points_geojson(self) -> dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                    "properties": {"id": p["id"], "lat": p["lat"], "lon": p["lon"]},
                }
                for p in self.user_points
            ],
        }

    @rx.var(cache=True)
    def user_points_vector_spec(self) -> dict[str, Any]:
        """Spec for _layers.py._build_vectors(). ``inline_data`` rather than a
        fetched ``path``: these points are session-specific, so there is no
        shared backend URL to fetch them from the way biomes/IFN are — the data
        is already in hand and travels with the rest of the page's reactive
        state, same channel as ``overlays`` (the study point's own rings).
        """
        return {
            "id": f"user_points_{self._user_points_version}",
            "dynamic": False,
            "inline_data": self.user_points_geojson,
            "z_index": 45,
            # A distinct colour from the IFN layer's red/orange — the two are
            # mutually exclusive on screen, but the palette should still read as
            # "a different kind of thing" at a glance in a screenshot or export.
            "point_style": {"radius": 5, "color": "#ffffff", "weight": 1.5,
                            "fillColor": "#5b5bd6", "fillOpacity": 0.95},
            "hover_style": {"radius": 8, "color": "#ffffff", "weight": 2.5,
                            "fillColor": "#8e8bf0", "fillOpacity": 1.0},
            "emit_hover": True,
            "emit_select": True,
        }
