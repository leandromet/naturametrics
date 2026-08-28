"""The workspace: map plus layer controls.

Phase 0 delivers the map and the layer machinery. The click → buffer → analysis
loop is Phase 1; the map component already emits ``on_map_click``, so wiring it
is a state change, not a component change.
"""

from __future__ import annotations

import reflex as rx

from ..components.conglomerado import conglomerado_card
from ..components.layer_panel import layer_panel
from ..components.layout import ACCENT, shell
from ..components.map import leaflet_map
from ..components.results import results_drawer
from ..state import AppState

#: Mirrors ``components/layout.py``'s own breakpoint scale
#: (``[initial, 30em, 48em, 62em]`` → phone, large phone, tablet, desktop) —
#: redefined here rather than imported to respect that module's own
#: leading-underscore "private to this file" convention.
_MOBILE_ONLY = ["flex", "flex", "flex", "none"]
_DESKTOP_ONLY = ["none", "none", "none", "flex"]

#: Shared drag/snap mechanics for the mobile bottom sheet. Ported from
#: camposcope's own ``_SHEET_SCRIPT`` (see that module's docstring for the
#: full design rationale: Pointer Events over mouse-only, document-level
#: delegation because the sheet's own content is conditionally rendered and
#: orphans direct listeners, `setPointerCapture` so a fast finger-drag
#: cannot lose the gesture). One difference from camposcope's version:
#: naturametrics has no desktop drag-to-resize precedent to preserve
#: (its desktop results panel has always been a fixed-height, non-draggable
#: box), so this app's script only ever drives one drawer, always in
#: "snap" mode — there is no free-drag branch to keep separate.
_SHEET_SCRIPT = """
(function () {
  if (window._nmSheetInit) return;
  window._nmSheetInit = true;

  var dragging = false, pointerId = null, startY = 0, startHeight = 0;
  var drawerEl = null;

  function snapPoints() {
    return [80, window.innerHeight * 0.45, window.innerHeight * 0.75];
  }

  function nearest(height, points) {
    var best = points[0], bestDist = Math.abs(height - points[0]);
    for (var i = 1; i < points.length; i++) {
      var d = Math.abs(height - points[i]);
      if (d < bestDist) { best = points[i]; bestDist = d; }
    }
    return best;
  }

  function settle(el, target) {
    el.style.transition = 'height 200ms ease-out';
    el.style.height = target + 'px';
    el.style.maxHeight = target + 'px';
    window.setTimeout(function () { el.style.transition = ''; }, 220);
    updateTab(el);
  }

  // The sheet's handle is a coloured tab with a chevron, not a plain bar
  // (see _drag_handle()) — it is the sheet's *only* "open" affordance now,
  // so it has to actually read as one. The chevron flips to point the way
  // dragging would go: up while still closer to peek, down once past it.
  function updateTab(el) {
    var tab = el.querySelector && el.querySelector('[data-sheet-tab]');
    if (!tab) return;
    var chevron = tab.querySelector('[data-chevron]');
    if (!chevron) return;
    chevron.style.transform = el.offsetHeight > 160 ? 'rotate(180deg)' : 'rotate(0deg)';
  }

  // Exposed so a Python event (a study point / conglomerado / drawn area
  // being selected) can ask the sheet to expand without needing to know
  // anything about drag state.
  window.__nmSheetSnapTo = function (name) {
    var el = document.getElementById('nm-mobile-sheet');
    if (!el) return;
    var pts = snapPoints();
    var target = name === 'full' ? pts[2] : name === 'peek' ? pts[0] : pts[1];
    // Never collapses an already-more-open sheet.
    if (el.offsetHeight >= target) return;
    settle(el, target);
  };

  document.addEventListener('pointerdown', function (e) {
    var handle = e.target.closest && e.target.closest('[data-drawer-handle]');
    if (!handle) return;
    var drawerId = handle.getAttribute('data-drawer-handle');
    drawerEl = document.getElementById(drawerId);
    if (!drawerEl) return;
    dragging = true;
    pointerId = e.pointerId;
    startY = e.clientY;
    startHeight = drawerEl.offsetHeight;
    try { handle.setPointerCapture(e.pointerId); } catch (err) { /* older browsers */ }
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('pointermove', function (e) {
    if (!dragging || e.pointerId !== pointerId || !drawerEl) return;
    var delta = startY - e.clientY;
    var next = Math.min(window.innerHeight * 0.75, Math.max(80, startHeight + delta));
    drawerEl.style.height = next + 'px';
    drawerEl.style.maxHeight = next + 'px';
    updateTab(drawerEl);
  });

  function end(e) {
    if (!dragging || e.pointerId !== pointerId || !drawerEl) return;
    dragging = false;
    document.body.style.userSelect = '';
    settle(drawerEl, nearest(drawerEl.offsetHeight, snapPoints()));
    drawerEl = null;
  }
  document.addEventListener('pointerup', end);
  document.addEventListener('pointercancel', end);

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    var active = document.activeElement;
    var handle = active && active.closest &&
      active.closest('[data-drawer-handle]');
    if (!handle) return;
    var drawer = document.getElementById(handle.getAttribute('data-drawer-handle'));
    if (!drawer) return;
    var pts = snapPoints();
    var idx = pts.indexOf(nearest(drawer.offsetHeight, pts));
    idx = e.key === 'ArrowUp' ? Math.min(pts.length - 1, idx + 1) : Math.max(0, idx - 1);
    settle(drawer, pts[idx]);
    e.preventDefault();
  });

  var initial = document.getElementById('nm-mobile-sheet');
  if (initial) updateTab(initial);
})();
"""


def _drag_handle() -> rx.Component:
    """A solid, accent-coloured tab with a chevron — not a plain grey bar,
    which turned out not to read as an interactive control at all (a real
    report: the sheet opened correctly on drag, but nobody found it without
    already knowing to try). This is now the sheet's only "open" affordance
    — the header's old hamburger button is gone, since there is no separate
    thing left for it to open."""
    return rx.box(
        rx.box(
            rx.icon("chevron-up", size=16, color="white",
                   custom_attrs={"data-chevron": "1"},
                   style={"transition": "transform 200ms ease"}),
            custom_attrs={"data-sheet-tab": "1"},
            display="flex", align_items="center", justify_content="center",
            width="56px", height="22px",
            background=f"var(--{ACCENT}-9)",
            border_radius="11px",
            box_shadow="0 2px 6px rgba(0, 0, 0, 0.3)",
        ),
        id="nm-mobile-sheet-handle",
        custom_attrs={"data-drawer-handle": "nm-mobile-sheet"},
        tab_index=0,
        role="slider",
        aria_label=AppState.tr["sheet_handle_aria"],
        outline="none",
        display="flex", justify_content="center", align_items="center",
        width="100%", height="30px", cursor="ns-resize", flex_shrink="0",
        padding_top="4px",
        _focus_visible={"background": "var(--gray-4)",
                        "box_shadow": "inset 0 0 0 2px var(--accent-8)"},
    )


def _mobile_sheet() -> rx.Component:
    """Below desktop: the map's only interaction surface — one draggable
    bottom sheet holding both what used to be the overlay sidebar
    (``layer_panel()``) and the results drawer, always mounted (peek/half/
    full, no separate open/close state — see ``_SHEET_SCRIPT``).

    ``position: fixed`` to the viewport, not ``absolute`` to a positioned
    ancestor: this sheet needs to float over the map regardless of the
    map's own layout mode, and unlike ``absolute`` it does not require the
    map's box to also be a positioning context — it simply covers the
    bottom of whatever is on screen below the header.
    """
    return rx.vstack(
        _drag_handle(),
        rx.box(
            layer_panel(),
            results_drawer(),
            overflow_y="auto", flex="1", min_height="0",
        ),
        id="nm-mobile-sheet",
        display=_MOBILE_ONLY,
        flex_direction="column",
        position="fixed", bottom="0", left="0", right="0",
        height="45vh", max_height="45vh",
        background="var(--color-panel-solid)",
        border_top_left_radius="var(--radius-4)",
        border_top_right_radius="var(--radius-4)",
        box_shadow="0 -4px 24px rgba(0, 0, 0, 0.25)",
        z_index="1000",
        overflow="hidden",
        spacing="0",
    )


def map_pane() -> rx.Component:
    return rx.box(
        conglomerado_card(),
        leaflet_map(
            id="nm-map",
            center=AppState.map_center,
            zoom=AppState.map_zoom,
            bounds=AppState.map_bounds,
            swipe=AppState.compare_mode != "off",
            layers=AppState.map_layers,
            overlays=AppState.buffer_overlays,
            vectors=AppState.map_vectors,
            fit_bounds=AppState.fit_bounds,
            on_map_click=AppState.set_study_point,
            on_point_hover=AppState.preview_conglomerado,
            on_point_select=AppState.select_conglomerado,
            area_select=AppState.multi_mode,
            on_area_select=AppState.select_multi_area,
            draw_enabled=AppState.draw_mode,
            on_geometry_drawn=AppState.on_geometry_drawn,
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        # Leaflet needs a positioned, sized container or it renders one grey tile.
        position="absolute",
        top="0",
        left="0",
    )


def workspace_main() -> rx.Component:
    """One map, one flex column, every breakpoint — not two different
    layouts. Below desktop the map is the column's only visible flex
    child (``results_drawer()``'s desktop sibling is ``display: none``,
    which contributes zero layout size) so it fills the full available
    height; the mobile sheet floats over it as a ``position: fixed``
    overlay that does not participate in this flow at all. At desktop the
    original arrangement is untouched: the map shares the column with
    ``results_drawer()`` sitting below it in normal flow, flex-shrinking
    the map exactly as it always did.

    **Exactly one ``leaflet_map`` instance.** ``layer_panel()`` and
    ``results_drawer()`` are safe to render twice — once inside the mobile
    sheet, once (via ``shell()``'s desktop sidebar box, and below) for
    desktop — because neither holds client-side state of its own; both are
    pure presentations of the same central ``AppState``, the same pattern
    the old code already relied on (``layer_panel()`` was passed into both
    the desktop static box and the old mobile drawer). The map is not like
    that: it wraps a real, persistent Leaflet instance (see
    ``components/map/leaflet_map.js``'s own "one persistent instance"
    decision), so it is built exactly once here, never duplicated between
    a mobile and a desktop branch.
    """
    return rx.vstack(
        rx.box(
            map_pane(),
            width="100%",
            flex="1 1 auto",
            min_height="0",
            position="relative",
        ),
        rx.box(
            results_drawer(),
            display=_DESKTOP_ONLY,
        ),
        _mobile_sheet(),
        width="100%",
        height="100%",
        spacing="0",
        align_items="stretch",
        on_mount=rx.call_script(_SHEET_SCRIPT),
    )


def index() -> rx.Component:
    return shell(sidebar=layer_panel(), main=workspace_main())
