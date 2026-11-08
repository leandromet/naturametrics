"""USA page state.

``WorldState`` is a **separate root state**, not a mixin added to the Brazil
page's ``AppState``. Reflex roots own their own vars, and the two pages disagree
about almost every one of them — the year range, what a layer toggle means, what
counts as a valid coordinate. Sharing a root would mean every var carrying a
"which country am I" qualifier, which is how the two pages would start breaking
each other.

The one thing that genuinely is shared — the chosen UI language — is handled by
:class:`WorldUIMixin` reading a query parameter rather than by a common parent,
so the link between the pages carries the language and nothing else does.

Same rule as the Brazil state: never store ``ee.Geometry`` or ``ee.Image`` in a
state var. State holds GeoJSON dicts and plain values; Earth Engine objects are
rebuilt inside service functions.
"""

from __future__ import annotations

import reflex as rx

from ._analysis import WorldAnalysisMixin
from ._export import WorldExportMixin
from ._gbif import WorldGbifMixin
from ._layers import WorldLayersMixin
from ._point import WorldPointMixin
from ._climate import WorldClimateMixin
from ._search import WorldSearchMixin
from ._ui import WorldUIMixin


class WorldState(WorldAnalysisMixin, WorldClimateMixin, WorldExportMixin, WorldGbifMixin,
                  WorldLayersMixin, WorldPointMixin, WorldSearchMixin,
                  WorldUIMixin, rx.State):
    """Root state for the ``/usa`` route."""


__all__ = ["WorldState"]
