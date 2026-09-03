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
      max-width: 390px;
    }
    .nm-vector-tip .nm-tip-row,
    .nm-vector-popup .nm-tip-row { display: flex; gap: 8px; justify-content: space-between; align-items: flex-start; }
    .nm-vector-tip .nm-tip-row + .nm-tip-row,
    .nm-vector-popup .nm-tip-row + .nm-tip-row {
      margin-top: 5px;
      padding-top: 5px;
      border-top: 1px solid rgba(0,0,0,.1);
    }
    .nm-vector-tip .nm-tip-row:first-child,
    .nm-vector-popup .nm-tip-row:first-child { font-weight: 600; }
    .nm-vector-tip .nm-tip-label,
    .nm-vector-popup .nm-tip-label { color: #60646c; white-space: nowrap; flex-shrink: 0; }
    .nm-vector-tip .nm-tip-value,
    .nm-vector-popup .nm-tip-value { text-align: left; }
    .nm-vector-popup .nm-tip-value a {
      color: var(--accent-9, #2a6f4f);
      font-weight: 600;
      text-decoration: none;
    }
    .nm-vector-popup .nm-tip-value a:hover { text-decoration: underline; }
    /* Fixed-open click popup for point layers (e.g. GBIF occurrences): same
       row styling as the hover tooltip above, but content stays selectable
       so it can be copied — the hover tooltip is deliberately not
       user-selectable since it disappears the moment the cursor that would
       select it moves. */
    .nm-vector-popup .leaflet-popup-content-wrapper {
      border-radius: 6px;
    }
    .nm-vector-popup .leaflet-popup-content {
      font: 12px/1.45 Inter, system-ui, sans-serif;
      color: #1c2024;
      margin: 10px 14px;
      user-select: text;
    }
    /* The "new study area" action tooltipHtml prepends when spec.offer_select
       is set — a real button rather than a styled link, since it performs an
       action (recentre the study area) rather than navigating anywhere. */
    .nm-vector-popup .nm-tip-select-btn {
      display: block;
      width: 100%;
      margin: -10px -14px 8px;
      padding: 7px 14px;
      border: none;
      border-bottom: 1px solid rgba(0,0,0,.1);
      background: var(--accent-3, #eaf3ee);
      color: var(--accent-11, #1b4332);
      font: 600 12px/1.3 Inter, system-ui, sans-serif;
      text-align: left;
      cursor: pointer;
      border-radius: 6px 6px 0 0;
    }
    .nm-vector-popup .nm-tip-select-btn:hover {
      background: var(--accent-4, #dcece3);
    }
    .nm-vector-label {
      font: 600 11px/1.25 Inter, system-ui, sans-serif;
      color: #ffffff;
      text-shadow: 0 1px 2px rgba(0,0,0,.85), 0 0 4px rgba(0,0,0,.6);
      white-space: normal;
      overflow-wrap: break-word;
      text-align: center;
      max-width: 92px;
      opacity: 0.9;
      transform: translate(-50%, -50%);
      pointer-events: none;
      letter-spacing: 0.01em;
    }
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
        vectors: browser-side vector layer specs (see ``services.biomes`` and
            ``services.ifn.vector_spec``).
        fit_bounds: ``[[s, w], [n, e]]`` re-applied whenever it changes.
        on_map_click: called with ``(lat, lon)`` when the user clicks the map.
        on_point_hover: called with a conglomerado's properties when the cursor
            rests on one, and with ``{}`` when it leaves. Debounced in the hook,
            because each call costs an Earth Engine query.
        on_point_select: called with a conglomerado's properties when one is
            clicked. Carries the point's *own* coordinates, not the click's.
        area_select: arm Ctrl/Cmd-drag area selection.
        on_area_select: called with ``{west, south, east, north}`` after such a drag.
    """

    # Leaflet itself — not imported at module scope in JS, but the package must
    # be installed for the dynamic import inside the hook to resolve.
    lib_dependencies: list[str] = ["leaflet@1.9.4", "leaflet-draw@1.0.4"]

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
    #: Arms Ctrl/Cmd-drag area selection. Off by default so the modifier does
    #: nothing surprising outside multiple-selection mode.
    area_select: Var[bool] = Var.create(False)
    #: Arms the polygon/rectangle draw toolbar. Off by default: a plain map
    #: click means "pick a point" everywhere else in this app, and the click
    #: that FINISHES a drawn shape must not also be read as one — see the
    #: click handler in leaflet_map.js for the bug this guards against.
    draw_enabled: Var[bool] = Var.create(False)
    #: ``[[south, west], [north, east]]``. Unlike ``bounds`` this is re-applied
    #: every time it CHANGES, so Python can frame a new selection. Set it to []
    #: to leave the view alone.
    fit_bounds: Var[Sequence[Sequence[float]]] = Var.create([])

    on_map_click: EventHandler[passthrough_event_spec(float, float)]
    on_point_hover: EventHandler[passthrough_event_spec(dict)]
    on_point_select: EventHandler[passthrough_event_spec(dict)]
    on_area_select: EventHandler[passthrough_event_spec(dict)]
    #: Called with a GeoJSON Feature when the draw toolbar finishes a
    #: polygon/rectangle. ``None`` is accepted but never sent by the hook
    #: today — see GeometryMixin.on_geometry_drawn for why.
    on_geometry_drawn: EventHandler[passthrough_event_spec(dict)]
    #: Called with ``{id, ...FeatureCollection.properties}`` after a dynamic
    #: vector layer whose spec sets ``emit_meta`` finishes a fetch. Describes
    #: the fetch, not a feature: how many records matched upstream against how
    #: many came back. Only services/gbif.py sets ``emit_meta`` — a layer that
    #: returns everything in view has nothing to report, and a state round-trip
    #: per pan for every dynamic layer would undo the reason they are fetched
    #: over HTTP rather than pushed through state.
    on_layer_meta: EventHandler[passthrough_event_spec(dict)]

    def _exclude_props(self) -> list[str]:
        # These drive the hook, not DOM attributes. React would warn about all
        # of them and Leaflet would never see them.
        return [*super()._exclude_props(), "center", "zoom", "bounds", "swipe",
                "layers", "overlays", "vectors", "fit_bounds", "area_select",
                "draw_enabled", "on_map_click", "on_point_hover",
                "on_point_select", "on_area_select", "on_geometry_drawn",
                "on_layer_meta"]

    def add_imports(self) -> list[dict[str, Any]]:
        """Leaflet's and leaflet-draw's stylesheets, and the React hooks the
        injected code calls.

        The hooks are declared explicitly rather than relying on Reflex having
        imported them for something else on the same page — that would make this
        component's correctness depend on what happens to sit beside it.

        Returned as a **list** of import dicts rather than one merged dict: two
        bare-string CSS imports would collide on the same ``""`` key otherwise.
        """
        return [
            {
                "": "leaflet/dist/leaflet.css",
                "react": [ImportVar(tag="useEffect"), ImportVar(tag="useRef")],
                # Vector layers are fetched from the BACKEND, which in
                # development is a different origin from the frontend (8011 vs
                # 3010) and in production is the same one. `getBackendURL` is
                # the only thing that knows which, so the hook must not build
                # the URL itself.
                "$/utils/state": [ImportVar(tag="getBackendURL")],
                "$/env.json": [ImportVar(tag="env", is_default=True)],
            },
            {"": "leaflet-draw/dist/leaflet.draw.css"},
        ]

    def add_custom_code(self) -> list[str]:
        return [_HOOK_JS, _TOOLTIP_CSS_JS]

    def add_hooks(self) -> list[str | Var[str]]:
        ref = self.get_ref()
        if ref is None:
            raise ValueError(
                "LeafletMap needs a literal `id` so Reflex generates a ref for it."
            )

        def _handler(name: str) -> str:
            """Render one event trigger as a JS callable the hook can invoke."""
            trigger = self.event_triggers.get(name)
            if trigger is None:
                return "null"
            if isinstance(trigger, EventChain):
                return wrap(str(format_prop(trigger)).strip("{}"), "(")
            return str(trigger)

        handler = _handler("on_map_click")
        hover = _handler("on_point_hover")
        select = _handler("on_point_select")
        area = _handler("on_area_select")
        draw = _handler("on_geometry_drawn")
        layer_meta = _handler("on_layer_meta")

        config = (
            f"{{center: {self.center!s}, zoom: {self.zoom!s}, "
            f"bounds: ({self.bounds!s}).length ? {self.bounds!s} : null, "
            f"fitBounds: ({self.fit_bounds!s}).length ? {self.fit_bounds!s} : null, "
            f"areaSelect: {self.area_select!s}, "
            f"drawEnabled: {self.draw_enabled!s}, "
            f"swipe: {self.swipe!s}}}"
        )
        expr = (
            f"useNaturametricsMap({ref}, {config}, {self.layers!s}, "
            f"{self.overlays!s}, {self.vectors!s}, {handler}, {hover}, {select}, "
            f"{area}, {draw}, {layer_meta})"
        )
        return [
            Var(
                expr,
                _var_type="str",
                _var_data=VarData(position=Hooks.HookPosition.POST_TRIGGER),
            )
        ]


leaflet_map = LeafletMap.create
