"""USA page state.

``USState`` is a **separate root state**, not a mixin added to the Brazil
page's ``AppState``. Reflex roots own their own vars, and the two pages disagree
about almost every one of them — the year range, what a layer toggle means, what
counts as a valid coordinate. Sharing a root would mean every var carrying a
"which country am I" qualifier, which is how the two pages would start breaking
each other.

The one thing that genuinely is shared — the chosen UI language — is handled by
:class:`USUIMixin` reading a query parameter rather than by a common parent,
so the link between the pages carries the language and nothing else does.

Same rule as the Brazil state: never store ``ee.Geometry`` or ``ee.Image`` in a
state var. State holds GeoJSON dicts and plain values; Earth Engine objects are
rebuilt inside service functions.
"""

from __future__ import annotations

import reflex as rx

from ._analysis import USAnalysisMixin
from ._export import USExportMixin
from ._gbif import USGbifMixin
from ._layers import USLayersMixin
from ._point import USPointMixin
from ._search import USSearchMixin
from ._ui import USUIMixin


class USState(USAnalysisMixin, USExportMixin, USGbifMixin,
                  USLayersMixin, USPointMixin, USSearchMixin,
                  USUIMixin, rx.State):
    """Root state for the ``/usa`` route."""


__all__ = ["USState"]
