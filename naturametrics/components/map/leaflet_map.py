"""Persistent Leaflet map component.

Implements decision **D1** (doc/09-open-decisions.md): one Leaflet instance created
once and mutated in place, rather than Yvynation's regenerate-the-whole-Folium-document
approach. Python sends a declarative layer list; the JS hook in ``leaflet_map.js``
diffs it against the map. The viewport therefore survives every layer change, which
is what constraint C1 requires and what makes the year slider viable.

The hook is a real ``.js`` file (editor support, linting) injected as custom code
rather than imported by path — Reflex's module-alias resolution for package-local
assets is one less thing to depend on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import reflex as rx
from reflex.constants.compiler import Hooks
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.format import format_prop, wrap
from reflex.event import EventChain
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var, VarData

_HOOK_JS = (Path(__file__).parent / "leaflet_map.js").read_text(encoding="utf-8")

#: Styling for the vector-layer hover tooltip. Injected from JS rather than
#: shipped as a stylesheet asset: it is fifteen lines that belong to this
#: component, and an asset file would put them a directory away from the markup
#: that produces the class names. Guarded for server-side rendering, where there
#: is no document.
_TOOLTIP_CSS_JS = """
if (typeof document !== "undefined" && !document.getElementById("nm-vector-tip-css")) {
  const style = document.createElement("style");
  style.id = "nm-vector-tip-css";
  style.textContent = `
    .nm-vector-tip {
      font: 12px/1.45 Inter, system-ui, sans-serif;
      padding: 6px 9px;
      border: none;
      border-radius: 6px;
      box-shadow: 0 2px 10px rgba(0,0,0,.25);
      background: rgba(255,255,255,.97);
      color: #1c2024;
      max-width: 260px;
    }
    .nm-vector-tip .nm-tip-row { display: flex; gap: 8px; justify-content: space-between; }
    .nm-vector-tip .nm-tip-row:first-child { font-weight: 600; }
    .nm-vector-tip .nm-tip-label { color: #60646c; white-space: nowrap; }
    .nm-vector-tip .nm-tip-value { text-align: right; }
  `;
  document.head.appendChild(style);
}
"""


class LeafletMap(rx.el.Div):
    """A persistent Leaflet map.

    Args:
        center: ``[lat, lon]`` the map is centred on.
        zoom: initial zoom level.
        layers: ordered list of tile-layer specs. Each is a dict with
            ``id`` (stable identity — the diff key), ``url`` (XYZ template),
            and optionally ``opacity``, ``attribution``, ``z_index``,
            ``max_native_zoom``. List order is stacking order unless ``z_index``
            says otherwise.
        vectors: browser-side vector layer specs (see ``services.biomes``).
        fit_bounds: ``[[s, w], [n, e]]`` re-applied whenever it changes.
        on_map_click: called with ``(lat, lon)`` when the user clicks the map.
    """

    # Leaflet itself — not imported at module scope in JS, but the package must
    # be installed for the dynamic import inside the hook to resolve.
    lib_dependencies: list[str] = ["leaflet@1.9.4"]

    center: Var[Sequence[float]] = Var.create([-15.0, -52.0])
    zoom: Var[int] = Var.create(4)
    #: Optional ``[[south, west], [north, east]]``. When set, the initial view is
    #: fitted to it and ``center``/``zoom`` are ignored for framing.
    bounds: Var[Sequence[Sequence[float]]] = Var.create([])
    #: When true the map shows a draggable vertical divider; layers whose spec
    #: carries ``clip: "left"`` / ``"right"`` are clipped to their side of it.
    swipe: Var[bool] = Var.create(False)
    layers: Var[Sequence[dict[str, Any]]] = Var.create([])
    #: GeoJSON FeatureCollection drawn above the tiles: the study point and its
    #: buffer outlines. Features carry a ``role`` property that drives styling.
    overlays: Var[dict[str, Any]] = Var.create({})
    #: Browser-side vector layers, each fetched by the hook from a backend path
    #: rather than pushed through state — for layers that must answer "what is
    #: under the cursor", which a tile cannot. See services/biomes.py.
    vectors: Var[Sequence[dict[str, Any]]] = Var.create([])
    #: ``[[south, west], [north, east]]``. Unlike ``bounds`` this is re-applied
    #: every time it CHANGES, so Python can frame a new selection. Set it to []
    #: to leave the view alone.
    fit_bounds: Var[Sequence[Sequence[float]]] = Var.create([])

    on_map_click: EventHandler[passthrough_event_spec(float, float)]

    def _exclude_props(self) -> list[str]:
        # These drive the hook, not DOM attributes. React would warn about all
        # of them and Leaflet would never see them.
        return [*super()._exclude_props(), "center", "zoom", "bounds", "swipe",
                "layers", "overlays", "vectors", "fit_bounds", "on_map_click"]

    def add_imports(self) -> dict[str, Any]:
        """Leaflet's stylesheet, and the React hooks the injected code calls.

        The hooks are declared explicitly rather than relying on Reflex having
        imported them for something else on the same page — that would make this
        component's correctness depend on what happens to sit beside it.
        """
        return {
            "": "leaflet/dist/leaflet.css",
            "react": [ImportVar(tag="useEffect"), ImportVar(tag="useRef")],
            # Vector layers are fetched from the BACKEND, which in development
            # is a different origin from the frontend (8011 vs 3010) and in
            # production is the same one. `getBackendURL` is the only thing that
            # knows which, so the hook must not build the URL itself.
            "$/utils/state": [ImportVar(tag="getBackendURL")],
            "$/env.json": [ImportVar(tag="env", is_default=True)],
        }

    def add_custom_code(self) -> list[str]:
        return [_HOOK_JS, _TOOLTIP_CSS_JS]

    def add_hooks(self) -> list[str | Var[str]]:
        ref = self.get_ref()
        if ref is None:
            raise ValueError(
                "LeafletMap needs a literal `id` so Reflex generates a ref for it."
            )

        on_click = self.event_triggers.get("on_map_click")
        if on_click is None:
            handler = "null"
        elif isinstance(on_click, EventChain):
            handler = wrap(str(format_prop(on_click)).strip("{}"), "(")
        else:
            handler = str(on_click)

        config = (
            f"{{center: {self.center!s}, zoom: {self.zoom!s}, "
            f"bounds: ({self.bounds!s}).length ? {self.bounds!s} : null, "
            f"fitBounds: ({self.fit_bounds!s}).length ? {self.fit_bounds!s} : null, "
            f"swipe: {self.swipe!s}}}"
        )
        expr = (
            f"useNaturametricsMap({ref}, {config}, {self.layers!s}, "
            f"{self.overlays!s}, {self.vectors!s}, {handler})"
        )
        return [
            Var(
                expr,
                _var_type="str",
                _var_data=VarData(position=Hooks.HookPosition.POST_TRIGGER),
            )
        ]


leaflet_map = LeafletMap.create
