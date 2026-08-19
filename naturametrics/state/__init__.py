"""Application state.

``AppState`` is assembled from mixins, one per coherent slice, following the
pattern Yvynation arrived at (doc/02-architecture.md §4). Mixins are declared
``rx.State, mixin=True`` and carry no state of their own at class level.

**Rule:** never store ``ee.Geometry`` or ``ee.Image`` objects in state vars —
they are not serialisable. State holds GeoJSON dicts and plain values; Earth
Engine objects are rebuilt inside service functions.
"""

from __future__ import annotations

import reflex as rx

from ._analysis import AnalysisMixin
from ._conglomerado import ConglomeradoMixin
from ._export import ExportMixin
from ._layers import LayersMixin
from ._point import PointMixin
from ._ui import UIMixin


class AppState(AnalysisMixin, ConglomeradoMixin, ExportMixin, LayersMixin,
               PointMixin, UIMixin, rx.State):
    """Root application state."""


__all__ = ["AppState"]
