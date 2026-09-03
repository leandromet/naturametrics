// Persistent Leaflet map for Naturametrics.
//
// Decision D1 (doc/09-open-decisions.md): the map instance is created ONCE and
// never torn down. Python sends a declarative list of layers; this hook diffs
// that list against what is currently on the map and adds/removes/updates only
// what changed. The viewport is therefore never disturbed by a layer change,
// which is what makes the year slider usable (constraint C1).
//
// Leaflet is imported dynamically inside the effect rather than at module top
// level: it touches `window` on import, and this app server-side renders.
//
// NOTE: this file is injected verbatim into Reflex's generated page module, which
// imports React hooks as NAMED bindings (`import {useEffect, useRef} from "react"`).
// There is no `React` namespace object in scope - calling `React.useRef` here throws
// "React is not defined" at render. Use the bare hook names.

function useNaturametricsMap(containerRef, config, layers, overlays, vectors, onMapClick,
                             onPointHover, onPointSelect, onAreaSelect, onGeometryDrawn,
                             onLayerMeta) {
  const mapRef = useRef(null);
  const layerRegistry = useRef(new Map());
  const vectorRegistry = useRef(new Map());
  const vectorPending = useRef(new Set());
  // Fetched GeoJSON, kept across toggles: switching the biome layer off and
  // on again must not re-download half a megabyte.
  const vectorData = useRef(new Map());
  // The latest spec list, readable from inside an in-flight fetch: dragging the
  // opacity slider while half a megabyte of polygons is still downloading would
  // otherwise land the layer at the opacity it had when the fetch started, and
  // nothing would re-render to correct it.
  const vectorsRef = useRef(vectors);
  // Dynamic layers refetch as the map moves, so their handlers must be current
  // without re-registering Leaflet listeners on every render.
  const hoverRef = useRef(onPointHover);
  const selectRef = useRef(onPointSelect);
  // A dynamic layer's FeatureCollection carries `properties` describing the
  // fetch itself, not any one feature - how many features matched upstream
  // against how many were actually returned. The GBIF layer needs this: at its
  // zoom a viewport routinely holds tens of thousands of occurrences and the
  // API returns at most 300, so without reporting the real total back the
  // panel would show an arbitrary sample as if it were everything.
  const layerMetaRef = useRef(onLayerMeta);
  const hoverTimer = useRef(null);
  const leaveTimer = useRef(null);
  const moveTimer = useRef(null);
  //: Last fetch key per dynamic layer - "same viewport, same filters, skip".
  const dynamicKey = useRef(new Map());
  //: When a conglomerado was last clicked. See the click handler below.
  const pointClickAt = useRef(0);
  //: The Leaflet module, so helpers outside the async effects can use L.
  const leafletRef = useRef(null);
  const areaRef = useRef(onAreaSelect);
  const areaEnabledRef = useRef(false);
  const overlayRef = useRef(null);
  const clickRef = useRef(onMapClick);
  const readyRef = useRef(false);
  const drawRef = useRef(onGeometryDrawn);
  //: True while the draw toolbar is armed (state/_geometry.py's draw_mode,
  //: via the sidebar switch) — every "a click/tap means pick a point" path
  //: checks this and backs off, so a drawing gesture is never also read as
  //: one. See the plain map click handler below for the bug this fixes.
  const drawEnabledRef = useRef(false);

  // Keep the click callback current without re-registering the Leaflet handler.
  clickRef.current = onMapClick;
  vectorsRef.current = vectors;
  hoverRef.current = onPointHover;
  selectRef.current = onPointSelect;
  layerMetaRef.current = onLayerMeta;
  areaRef.current = onAreaSelect;
  areaEnabledRef.current = !!(config && config.areaSelect);
  drawRef.current = onGeometryDrawn;
  drawEnabledRef.current = !!(config && config.drawEnabled);

  // --- 1. Create the map exactly once -------------------------------------
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const mod = await import("leaflet");
      const L = mod.default || mod;
      if (cancelled || mapRef.current || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        preferCanvas: true,      // canvas rendering - needed for thousands of IFN points
        zoomControl: true,
        worldCopyJump: false,
        attributionControl: true,
        // Brazil is nearly square (~41 deg x 40 deg) but the map pane is
        // landscape, so height binds. With Leaflet's default integer zoomSnap,
        // fitBounds rounds DOWN a whole level and the country ends up surrounded
        // by two oceans. Quarter-level snapping fits it snugly; tile scaling at
        // 0.25 steps is not noticeable at these zooms.
        zoomSnap: 0.25,
        zoomDelta: 1,
      });

      // Prefer bounds over a fixed zoom: a hard-coded zoom that frames Brazil on
      // a 1440px screen clips Roraima and Rio Grande do Sul on a smaller one.
      // fitBounds adapts, and it is the same primitive used to frame a buffer
      // set or an IFN point.
      if (config.bounds) {
        map.fitBounds(config.bounds, {padding: [12, 12]});
      } else {
        map.setView(config.center, config.zoom);
      }

      L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

      map.on("click", (e) => {
        // A click that landed on a conglomerado has already been handled, with
        // that conglomerado's own coordinates. Without this the map would then
        // overwrite the study point with the cursor position.
        if (Date.now() - pointClickAt.current < 150) return;
        // While the draw toolbar is armed, a click is either placing a
        // polygon vertex or finishing a shape (rectangle's second corner) —
        // never "pick a point here". Without this, releasing the mouse to
        // finish a drawn shape also ran the point analysis for that spot.
        if (drawEnabledRef.current) return;
        if (clickRef.current) {
          clickRef.current(
            Math.round(e.latlng.lat * 1e6) / 1e6,
            Math.round(e.latlng.lng * 1e6) / 1e6
          );
        }
      });

      leafletRef.current = L;
      mapRef.current = map;
      readyRef.current = true;

      // The buffer preview is clipped in LAYER-PIXEL space, so panning or
      // zooming invalidates it. Bound here rather than inside the swipe effect
      // (which binds the same handler for its own divider) because the preview
      // has to track the map whether or not the swipe is on.
      const onClipUpdate = () => { applyClips(); applyLabelVisibility(); };
      map.on("move zoom zoomend moveend resize viewreset", onClipUpdate);
      map._nmClipUpdate = onClipUpdate;

      // Expose the instance on the container: an imperative handle for fly-to
      // (jumping to an IFN point or a pasted coordinate), and it makes the map
      // inspectable from the browser console and from the Playwright tests.
      containerRef.current._nmMap = map;

      // The container is often still being laid out on first paint; without
      // this Leaflet computes a zero-size viewport and renders one grey tile.
      const settle = () => map.invalidateSize();
      setTimeout(settle, 0);
      setTimeout(settle, 250);
      window.addEventListener("resize", settle);
      map._nmSettle = settle;
    })();

    return () => {
      cancelled = true;
      const map = mapRef.current;
      if (map) {
        if (map._nmSettle) window.removeEventListener("resize", map._nmSettle);
        if (map._nmClipUpdate) map.off("move zoom zoomend moveend resize viewreset",
                                       map._nmClipUpdate);
        if (containerRef.current) containerRef.current._nmMap = null;
        map.remove();
        mapRef.current = null;
        overlayRef.current = null;
        readyRef.current = false;
        layerRegistry.current.clear();
        vectorRegistry.current.clear();
        vectorPending.current.clear();
        dynamicKey.current.clear();
        [hoverTimer, leaveTimer, moveTimer].forEach((t) => {
          if (t.current) clearTimeout(t.current);
          t.current = null;
        });
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- 1b. Draw toolbar: a polygon/rectangle study region -------------------
  // Draw-only — no edit/remove sub-toolbar, and the completed shape is never
  // kept in its own layer group. Python's on_geometry_drawn echoes it straight
  // back through `overlays` (the "drawn_region" role, styled in section 3
  // below) exactly like a pasted WKT or an uploaded KML — one rendering path
  // for "a region is on screen", so nothing here has to stay in sync with it.
  // Clearing goes through the sidebar's "Limpar" button instead, which already
  // flows through that same overlays channel.
  //
  // The library is imported once, eagerly, the first time this runs —
  // regardless of whether the toolbar is shown yet — because
  // L.Draw.Event.CREATED (bound at the same time) has to exist before ANY
  // draw can complete. Only the toolbar CONTROL itself (the visible corner
  // buttons) is added or removed as drawEnabled changes.
  const drawEnabled = !!(config && config.drawEnabled);

  useEffect(() => {
    let cancelled = false;

    const attach = async () => {
      const map = mapRef.current;
      const L = leafletRef.current;
      if (!map || !L) return false;

      if (!map._nmDrawImported) {
        // Side-effecting import: leaflet-draw has no exports of its own, it
        // attaches L.Control.Draw/L.Draw onto the SAME Leaflet module already
        // imported above (module dedup makes this the identical instance).
        await import("leaflet-draw");
        if (cancelled || !mapRef.current) return false;
        map._nmDrawImported = true;

        map.on(L.Draw.Event.CREATED, (e) => {
          // The mouseup that finishes a shape (a rectangle's second corner,
          // a polygon's closing click) also reaches the map's own "click"
          // handler a moment later — this is the same suppression mechanism
          // that handler already uses for conglomerado clicks.
          pointClickAt.current = Date.now();
          if (drawRef.current) drawRef.current(e.layer.toGeoJSON());
        });
      }

      if (drawEnabled) {
        if (map._nmDrawControl) return true;
        const drawControl = new L.Control.Draw({
          position: "topright",
          draw: {
            // showArea: false on both — leaflet-draw 1.0.4's readableArea()
            // does an unguarded `type = 'sqm'` assignment (no var/let/const)
            // that throws a ReferenceError under strict mode (which ES module
            // builds run under). That throw happens INSIDE _onMouseMove,
            // before it reaches _drawShape(latlng) — so the shape's bounds
            // never update during the drag and freeze at whatever tiny size
            // existed on the first mousemove. Turning the area tooltip off
            // skips the call to readableArea() entirely, which is the only
            // way to avoid the crash short of vendoring a patched copy of the
            // library.
            polygon: {
              allowIntersection: false,
              showArea: false,
              shapeOptions: {color: "#8e4ec6", weight: 2.5},
            },
            rectangle: {showArea: false, shapeOptions: {color: "#8e4ec6", weight: 2.5}},
            marker: false,
            circle: false,
            circlemarker: false,
            polyline: false,
          },
          edit: false,
        });
        map.addControl(drawControl);
        map._nmDrawControl = drawControl;
      } else if (map._nmDrawControl) {
        map.removeControl(map._nmDrawControl);
        map._nmDrawControl = null;
      }
      return true;
    };

    if (readyRef.current) {
      attach();
    } else {
      const t = setInterval(() => {
        if (readyRef.current) {
          clearInterval(t);
          attach();
        }
      }, 50);
      return () => {
        cancelled = true;
        clearInterval(t);
      };
    }

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawEnabled]);

  // --- 2. Diff the tile-layer list against what is on the map --------------
  const layerKey = JSON.stringify(layers);

  useEffect(() => {
    let cancelled = false;

    const sync = async () => {
      const map = mapRef.current;
      if (!map || cancelled) return;

      const mod = await import("leaflet");
      const L = mod.default || mod;
      if (cancelled || !mapRef.current) return;

      const registry = layerRegistry.current;
      const incoming = Array.isArray(layers) ? layers : [];
      const wanted = new Set(incoming.map((spec) => spec.id));

      // Remove layers no longer requested.
      for (const [id, entry] of Array.from(registry.entries())) {
        if (!wanted.has(id)) {
          map.removeLayer(entry.layer);
          registry.delete(id);
        }
      }

      // Add or update the rest, preserving list order as stacking order.
      incoming.forEach((spec, index) => {
        const existing = registry.get(spec.id);
        const zIndex = spec.z_index != null ? spec.z_index : index;

        if (existing && existing.url === spec.url) {
          // Same source - only cheap properties may have changed.
          if (existing.opacity !== spec.opacity) {
            existing.layer.setOpacity(spec.opacity);
            existing.opacity = spec.opacity;
          }
          if (existing.zIndex !== zIndex) {
            existing.layer.setZIndex(zIndex);
            existing.zIndex = zIndex;
          }
          if (existing.clip !== (spec.clip || null)) {
            existing.clip = spec.clip || null;
            applyClips();
          }
          if (existing.clipRadiusKm !== spec.clip_radius_km ||
              existing.clipShape !== spec.clip_shape) {
            existing.clipRadiusKm = spec.clip_radius_km;
            existing.clipShape = spec.clip_shape;
            applyClips();
          }
          // The preview follows the cursor from conglomerado to conglomerado, so
          // the circle moves far more often than the tile source changes.
          const nextCircles = JSON.stringify(spec.clip_circles || null);
          if (JSON.stringify(existing.clipCircles || null) !== nextCircles) {
            existing.clipCircles = spec.clip_circles || null;
            existing.clipRadiusKm = spec.clip_radius_km;
            existing.clipShape = spec.clip_shape;
            applyClips();
          }
          return;
        }

        // URL changed (or brand new): the tile source is different, so the
        // layer has to be replaced rather than mutated.
        if (existing) {
          map.removeLayer(existing.layer);
          registry.delete(spec.id);
        }

        const layer = L.tileLayer(spec.url, {
          opacity: spec.opacity != null ? spec.opacity : 1.0,
          attribution: spec.attribution || "",
          maxNativeZoom: spec.max_native_zoom || 18,
          maxZoom: 22,
          zIndex: zIndex,
          crossOrigin: true,
        });
        layer.addTo(map);
        registry.set(spec.id, {
          layer: layer,
          url: spec.url,
          opacity: spec.opacity,
          zIndex: zIndex,
          clip: spec.clip || null,
          clipCircles: spec.clip_circles || null,
          clipRadiusKm: spec.clip_radius_km,
          clipShape: spec.clip_shape,
        });
      });

      applyClips();
    };

    if (readyRef.current) {
      sync();
    } else {
      // Map not built yet - run the sync as soon as it is ready.
      const t = setInterval(() => {
        if (readyRef.current) {
          clearInterval(t);
          sync();
        }
      }, 50);
      return () => {
        cancelled = true;
        clearInterval(t);
      };
    }

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layerKey]);

  // --- 2b. Swipe comparison ------------------------------------------------
  // Two MapBiomas years on screen at once, split by a draggable vertical line.
  // The divider is dragged and the clip recomputed entirely in the browser: a
  // round-trip to Python per mouse-move would make it lag, and the split
  // position is a viewing preference with no analytical meaning, so the backend
  // does not need to know about it.
  const swipeRef = useRef(0.5);

  // Clipping is done with the legacy `clip: rect(...)` in LAYER-PIXEL space, not
  // with `clip-path: inset(%)`.
  //
  // The reason is subtle: a `.leaflet-layer` container has no intrinsic size.
  // Leaflet leaves it at 0x0 and positions tiles as absolutely-placed children
  // that extend well outside it. Percentages in `clip-path: inset()` resolve
  // against that 0x0 reference box, so ANY inset clips the entire layer away -
  // both halves simply vanish, with the tiles still in the DOM and fully
  // loaded, which looks like a data problem rather than a CSS one.
  //
  // `clip: rect()` takes absolute pixel offsets in the element's own coordinate
  // system (the tile-layer origin), so it is unaffected by the empty box. The
  // coordinates therefore have to be recomputed whenever the map moves or
  // zooms - see the map event bindings below. Same approach as
  // leaflet-side-by-side.
  // A buffer's centre and radius, in the same layer-pixel space the clips use.
  //
  // The radius is measured by projecting a point due east of the centre rather
  // than from a metres-per-pixel constant: Web Mercator's scale factor varies
  // with latitude, and a circle drawn with the equator's scale would be visibly
  // too small in Rio Grande do Sul. Mercator is conformal, so a small circle on
  // the ground stays a circle on screen and one radius is enough.
  const bufferClipGeometry = (map, centreLatLon, radiusKm) => {
    const L = leafletRef.current;
    if (!L || !centreLatLon) return null;
    const {lat, lon} = centreLatLon;
    const centre = map.latLngToLayerPoint(L.latLng(lat, lon));
    const metresPerDegreeLon = 111320 * Math.cos(lat * Math.PI / 180);
    if (!(metresPerDegreeLon > 1)) return null;
    const edge = map.latLngToLayerPoint(
      L.latLng(lat, lon + (radiusKm * 1000) / metresPerDegreeLon)
    );
    const radius = Math.abs(edge.x - centre.x);
    if (!(radius > 0) || !isFinite(radius)) return null;
    return {x: centre.x, y: centre.y, r: radius};
  };

  // One circle as an SVG path subpath: two half-arcs, which is the standard way
  // to write a full circle in path syntax (a single 360 deg arc is degenerate).
  const circleSubpath = (g) =>
    `M ${g.x - g.r} ${g.y} ` +
    `a ${g.r} ${g.r} 0 1 0 ${2 * g.r} 0 ` +
    `a ${g.r} ${g.r} 0 1 0 ${-2 * g.r} 0 Z`;

  const squareSubpath = (g) => {
    const half = g.r;
    return `M ${g.x - half} ${g.y - half} ` +
      `L ${g.x + half} ${g.y - half} ` +
      `L ${g.x + half} ${g.y + half} ` +
      `L ${g.x - half} ${g.y + half} Z`;
  };

  const applyClips = () => {
    const map = mapRef.current;
    if (!map) return;

    const size = map.getSize();
    const nw = map.containerPointToLayerPoint([0, 0]);
    const se = map.containerPointToLayerPoint([size.x, size.y]);
    const frac = Math.max(0, Math.min(1, swipeRef.current));
    const splitX = nw.x + size.x * frac;

    layerRegistry.current.forEach((entry) => {
      const el = entry.layer.getContainer && entry.layer.getContainer();
      if (!el) return;
      // Both properties are reset every pass: a layer that used to be clipped
      // and no longer is must lose the clip, and the two mechanisms must never
      // be left set at the same time (clip-path wins and `clip` is ignored).
      el.style.clipPath = "";
      el.style.clip = "";

      if (entry.clipCircles && entry.clipCircles.length) {
        const radiusKm = entry.clipRadiusKm;
        const shapes = entry.clipCircles
          .map((c) => bufferClipGeometry(map, c, radiusKm))
          .filter(Boolean);
        if (!shapes.length) return;

        if (shapes.length === 1 &&
            (entry.clipShape === "bbox" || entry.clipShape === "square")) {
          const g = shapes[0];
          const half = g.r;
          // rect(top, right, bottom, left) — the legacy property, which takes
          // absolute offsets in the element's own coordinate system and is
          // therefore immune to the 0×0 reference box explained below. Only ever
          // one rectangle, so a multiple selection falls through to the path.
          el.style.clip = `rect(${g.y - half}px, ${g.x + half}px, ` +
                          `${g.y + half}px, ${g.x - half}px)`;
        } else if (shapes.length === 1) {
          // Absolute lengths, not percentages: the reason `clip-path: inset(%)`
          // fails here is that percentages resolve against a 0×0 box, and `px`
          // values do not.
          const g = shapes[0];
          el.style.clipPath = `circle(${g.r}px at ${g.x}px ${g.y}px)`;
        } else {
          // Many buffers: one path with a subpath per circle. clip-path takes
          // the union of the subpaths, so overlapping buffers merge rather than
          // punching holes in each other (which is what the even-odd fill rule
          // would do, and is why the rule is left at its nonzero default).
          const subpath = entry.clipShape === "square"
            ? squareSubpath : circleSubpath;
          el.style.clipPath = `path("${shapes.map(subpath).join(" ")}")`;
        }
        return;
      }

      if (entry.clip === "left") {
        el.style.clip = `rect(${nw.y}px, ${splitX}px, ${se.y}px, ${nw.x}px)`;
      } else if (entry.clip === "right") {
        el.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${splitX}px)`;
      }
    });

    const handle = map.getContainer().querySelector(".nm-swipe-handle");
    if (handle) handle.style.left = `${frac * 100}%`;
  };

  const swipeEnabled = !!(config && config.swipe);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const map = mapRef.current;
      if (!map) return;
      const container = map.getContainer();
      let handle = container.querySelector(".nm-swipe-handle");

      if (!swipeEnabled) {
        if (handle) {
          if (handle._nmCleanup) handle._nmCleanup();
          handle.remove();
        }
        applyClips();
        return;
      }
      if (handle) { applyClips(); return; }

      const mod = await import("leaflet");
      const L = mod.default || mod;
      if (cancelled || !mapRef.current) return;

      // The handle lives INSIDE the Leaflet container, so without this every
      // grab of the divider also reaches the map's own click handler and drops
      // a new study point underneath the cursor.
      handle = L.DomUtil.create("div", "nm-swipe-handle", container);
      // 24px of transparent grab area around a 2px visual line: a 2px target is
      // unusable with a mouse and impossible on touch.
      handle.style.cssText = [
        "position:absolute", "top:0", "bottom:0", "width:24px",
        "margin-left:-12px", "cursor:ew-resize", "z-index:700", "left:50%",
        "background:transparent", "touch-action:none",
      ].join(";");

      const line = L.DomUtil.create("div", "", handle);
      line.style.cssText = [
        "position:absolute", "top:0", "bottom:0", "left:11px", "width:2px",
        "background:#ffffff", "box-shadow:0 0 6px rgba(0,0,0,.6)",
        "pointer-events:none",
      ].join(";");

      const grip = L.DomUtil.create("div", "", handle);
      grip.style.cssText = [
        "position:absolute", "top:50%", "left:0", "width:24px", "height:32px",
        "transform:translateY(-50%)", "border-radius:4px", "background:#ffffff",
        "box-shadow:0 1px 6px rgba(0,0,0,.5)", "display:flex",
        "align-items:center", "justify-content:center",
        "font:600 12px system-ui", "color:#333", "user-select:none",
        "pointer-events:none",
      ].join(";");
      grip.textContent = "\u2551";

      // Stops mousedown/click/dblclick/touchstart from reaching the map, which
      // is what keeps a drag of the divider from registering as a map click.
      L.DomEvent.disableClickPropagation(handle);
      L.DomEvent.disableScrollPropagation(handle);

      let dragging = false;
      const setFromClientX = (clientX) => {
        const rect = container.getBoundingClientRect();
        swipeRef.current = (clientX - rect.left) / rect.width;
        applyClips();
      };
      const onDown = (e) => {
        dragging = true;
        map.dragging.disable();
        L.DomEvent.stop(e);
      };
      const onMove = (e) => {
        if (!dragging) return;
        setFromClientX(e.touches ? e.touches[0].clientX : e.clientX);
        if (e.cancelable) e.preventDefault();
      };
      const onUp = () => {
        if (!dragging) return;
        dragging = false;
        map.dragging.enable();
      };

      handle.addEventListener("mousedown", onDown);
      handle.addEventListener("touchstart", onDown, {passive: false});
      document.addEventListener("mousemove", onMove);
      document.addEventListener("touchmove", onMove, {passive: false});
      document.addEventListener("mouseup", onUp);
      document.addEventListener("touchend", onUp);

      // The clip rect is in layer pixels, so panning or zooming invalidates it.
      // Without this the split drifts across the screen as the map moves.
      const onMapMove = () => applyClips();
      map.on("move zoom zoomend moveend resize viewreset", onMapMove);

      handle._nmCleanup = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("touchmove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.removeEventListener("touchend", onUp);
        map.off("move zoom zoomend moveend resize viewreset", onMapMove);
        if (dragging) map.dragging.enable();
      };

      applyClips();
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [swipeEnabled, layerKey]);

  // --- 3. Vector overlays: study point + buffer rings ----------------------
  // Redrawn wholesale rather than diffed: an overlay set is a handful of
  // features that all change together when the user picks a new point, so
  // there is nothing to gain from diffing and a lot of state to get wrong.
  //
  // These live in their OWN pane, with `pointer-events: none`, and that is not
  // cosmetic. With preferCanvas each renderer draws into its own <canvas> and
  // binds mousemove to that element; a canvas is opaque to hit-testing, so the
  // topmost one over a pixel takes the event and the ones beneath never see it.
  // In the default overlayPane (z 400) this group sits above the conglomerados
  // (nmVectors, z 350) and silently kills their hover the moment the first
  // study point is chosen - while map clicks keep working, because those bubble
  // to the map container. Marking the individual paths `interactive: false` does
  // NOT prevent this; only the pane does.
  const overlayKey = JSON.stringify(overlays);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const map = mapRef.current;
      if (!map) return;
      const mod = await import("leaflet");
      const L = mod.default || mod;
      if (cancelled || !mapRef.current) return;

      if (!map.getPane("nmOverlays")) {
        const pane = map.createPane("nmOverlays");
        pane.style.zIndex = 450;
        pane.style.pointerEvents = "none";
      }

      if (overlayRef.current) {
        map.removeLayer(overlayRef.current);
        overlayRef.current = null;
      }
      if (!overlays || !overlays.features || !overlays.features.length) return;

      const group = L.geoJSON(overlays, {
        pane: "nmOverlays",
        // Buffer outlines must never swallow map clicks - the user has to be
        // able to click a new study point straight through them.
        interactive: false,
        style: (feature) => {
          const props = feature.properties || {};
          // A drawn/pasted/uploaded region (services/region_geometry.py) —
          // filled and in its own colour, unlike the buffer/full-area
          // outlines below: this is an exact user-supplied boundary, not a
          // preview the underlying land-cover layer needs to show through.
          if (props.role === "drawn_region") {
            return {
              color: "#8e4ec6", weight: 2.5, opacity: 0.95,
              fill: true, fillColor: "#8e4ec6", fillOpacity: 0.18,
            };
          }
          // The full-area rectangle (multi-select "área total") — outline
          // only, same reasoning as the per-point buffers below: a filled
          // box would hide whatever land-cover layer is on underneath it,
          // which is the one thing this overlay exists to let through.
          if (props.role === "full_area") {
            return {
              color: "#ffffff",
              weight: 2.5,
              opacity: 0.95,
              fill: false,
            };
          }
          if (props.role !== "buffer") return {};
          // A GBIF zone card's "show on map" button (state/_gbif.py's
          // show_gbif_zone) stamps this flag onto the one ring it means,
          // rather than this app tracking a second "which radius" value in
          // JS that could drift from the GeoJSON actually on screen.
          if (props.highlighted) {
            return {
              color: "#ffd166",
              weight: 4,
              opacity: 1,
              fill: false,
              dashArray: null,
            };
          }
          return {
            color: "#ffffff",
            weight: 2,
            opacity: 0.95,
            fill: false,
            dashArray: props.radius_km <= 1 ? null : "5,4",
          };
        },
        pointToLayer: (feature, latlng) => {
          const props = feature.properties || {};
          // A multiple selection sends its rings as centre+radius rather than as
          // polygons. 200 conglomerados x 4 rings x 128 vertices is megabytes of
          // coordinates over the WebSocket; this is three numbers per ring, and
          // Leaflet draws the circle itself.
          if (props.role === "buffer_circle") {
            return L.circle(latlng, {
              pane: "nmOverlays",
              radius: props.radius_m,
              color: "#ffffff",
              weight: 1.5,
              opacity: 0.9,
              fill: false,
              dashArray: props.radius_km <= 1 ? null : "5,4",
              interactive: false,
            });
          }
          return L.circleMarker(latlng, {
            pane: "nmOverlays",
            radius: props.role === "selected_point" ? 5 : 6,
            color: "#ffffff",
            weight: 2,
            fillColor: props.role === "selected_point" ? "#ff8a00" : "#e5484d",
            fillOpacity: 1,
            interactive: false,
          });
        },
      });
      group.addTo(map);
      overlayRef.current = group;
    })();

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlayKey]);


  // --- 3b. Browser-side vector layers -------------------------------------
  // Tiles cannot answer "what is under the cursor" - they are pixels. A layer
  // that has to name itself on hover, or be clicked, therefore needs real
  // geometry in the browser, so these specs carry a PATH and the hook fetches
  // the GeoJSON over plain HTTP (cacheable, gzipped, and off the WebSocket -
  // see naturametrics/api/__init__.py).
  //
  // Two kinds:
  //   * STATIC  (biomes) - fetched once, kept, never refetched.
  //   * DYNAMIC (IFN conglomerados) - `spec.dynamic`, refetched for the current
  //     viewport whenever the map settles, and removed entirely below
  //     `spec.min_zoom`. 17 000 points nationwide is not something to hand the
  //     browser as one payload, and below that zoom an individual dot is a
  //     pixel wide - hovering one would be an accident, not a choice.
  //
  // They live in their own pane between the tiles (200) and the overlay pane
  // (400): above the imagery they contextualise, below the study point and its
  // buffers, which must never be obscured.
  const vectorKey = JSON.stringify(vectors);

  const emitHover = (props) => {
    if (hoverRef.current) hoverRef.current(props || {});
  };

  const attachPointHandlers = (L, spec, featureLayer, feature, hasPopup) => {
    const props = (feature && feature.properties) || {};
    // pointStyleFor, not spec.point_style: on a layer that colours per feature
    // (spec.color_property) the flat style is only half the answer, and using
    // it here would repaint every dot to the fallback grey the first time the
    // cursor left it.
    const base = pointStyleFor(spec, feature);
    const over = spec.hover_style
      ? {...base, ...spec.hover_style, ...paletteFill(spec, feature)}
      : base;

    featureLayer.on("mouseover", () => {
      featureLayer.setStyle(over);
      if (featureLayer.bringToFront) featureLayer.bringToFront();
      if (!spec.emit_hover) return;
      if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
      // Debounced: sweeping the cursor across a screen of conglomerados must
      // not fire an Earth Engine query per dot. 350 ms is long enough that only
      // a deliberate pause counts as "I want to know about this one".
      hoverTimer.current = setTimeout(() => emitHover(props), 350);
    });

    featureLayer.on("mouseout", () => {
      featureLayer.setStyle(base);
      if (!spec.emit_hover) return;
      if (hoverTimer.current) { clearTimeout(hoverTimer.current); hoverTimer.current = null; }
      // Grace period before clearing: without it the card flickers out every
      // time the cursor crosses the gap between two adjacent points.
      if (leaveTimer.current) clearTimeout(leaveTimer.current);
      leaveTimer.current = setTimeout(() => emitHover({}), 600);
    });

    featureLayer.on("click", (e) => {
      // With preferCanvas the renderer dispatches from the map container, so
      // stopping propagation is not reliably enough on its own to keep the
      // map's own click handler from also dropping a study point a few metres
      // away. The timestamp below is what actually guarantees it.
      if (e && e.originalEvent) L.DomEvent.stop(e.originalEvent);
      // While the draw toolbar is armed, this is a polygon vertex landing on
      // a point/conglomerado, not a request to select it — same reasoning
      // as the plain map click handler's own drawEnabledRef check.
      if (drawEnabledRef.current) return;
      pointClickAt.current = Date.now();
      if (spec.emit_select && selectRef.current) {
        // The feature's OWN coordinates, not the click position: the user is
        // choosing a sampling location with a known identity, and analysing a
        // point 40 m away from it would quietly answer a different question.
        // Every property is spread through rather than a fixed whitelist, so
        // this same handler serves both the IFN layer's conglomerado/uf/
        // municipio/bioma/ponto_id shape and a pasted point's plain id — the
        // Python side (state/_conglomerado.py) is what interprets the shape,
        // not this hook.
        selectRef.current({...props, lat: props.lat, lon: props.lon});
      } else if (hasPopup) {
        // Pin this feature's own details open instead of forwarding the
        // click to the generic map-click handler, which would otherwise
        // recentre the whole study area on this exact dot. Reading a
        // record's details and choosing to study its coordinate are two
        // different intentions — offer_select's own button inside the popup
        // is how the second one is expressed, deliberately.
        featureLayer.openPopup();
      } else if (clickRef.current && e.latlng) {
        clickRef.current(Math.round(e.latlng.lat * 1e6) / 1e6,
                         Math.round(e.latlng.lng * 1e6) / 1e6);
      }
    });
  };

  const buildLayer = (L, spec, data) => {
    const geoLayer = L.geoJSON(data, {
      pane: "nmVectors",
      style: (feature) => (spec.point_style
        ? pointStyleFor(spec, feature)
        : styleFor(spec, feature)),
      pointToLayer: (feature, latlng) =>
        L.circleMarker(latlng, {...pointStyleFor(spec, feature), pane: "nmVectors"}),
      onEachFeature: (feature, featureLayer) => {
        const html = tooltipHtml(spec, feature);
        if (html) {
          // Points get an anchored tooltip; polygons get a sticky one that
          // follows the cursor - anchored to the centroid of the Amazon it
          // would be off-screen.
          featureLayer.bindTooltip(html, {
            sticky: !spec.point_style,
            direction: "top",
            offset: spec.point_style ? [0, -6] : [0, 0],
            opacity: 0.95,
            className: "nm-vector-tip",
          });
        }
        if (spec.point_style) {
          if (html) {
            // Bound alongside the hover tooltip, not instead of it: the
            // tooltip is the quick preview while sweeping the cursor across
            // a cluster of dots, the popup is what a click "fixes" open for
            // reading and copying. Leaflet's own close button and
            // one-popup-at-a-time auto-close give a dismiss-on-elsewhere-
            // click behaviour for free.
            featureLayer.bindPopup(html, {
              className: "nm-vector-popup",
              closeButton: true,
              autoClose: true,
              maxWidth: 390,
            });
            if (spec.offer_select) {
              // The select button is inert markup from tooltipHtml until
              // wired here — this is the one place that still has this
              // feature's own props in closure when the popup's DOM actually
              // exists (Leaflet builds it lazily, on open).
              featureLayer.on("popupopen", () => {
                const el = featureLayer.getPopup() && featureLayer.getPopup().getElement();
                const btn = el && el.querySelector(".nm-tip-select-btn");
                if (!btn) return;
                btn.onclick = () => {
                  // clickRef (set_study_point), not selectRef: selectRef is
                  // wired to select_conglomerado, which expects an IFN
                  // plot's own property shape (conglomerado/uf/municipio/
                  // bioma/ponto_id) — feeding it a GBIF record would either
                  // do nothing or misread the wrong fields. A plain map
                  // click recentring the study area on (lat, lon) is exactly
                  // what this button offers, so it reuses that handler.
                  const p = feature.properties || {};
                  if (clickRef.current && p.lat != null && p.lon != null) {
                    clickRef.current(p.lat, p.lon);
                  }
                  featureLayer.closePopup();
                };
              });
            }
          }
          attachPointHandlers(L, spec, featureLayer, feature, !!html);
        } else {
          // An interactive polygon swallows the click that would otherwise
          // reach the map, so the study-point selection has to be forwarded
          // explicitly or clicking anywhere on a biome does nothing.
          featureLayer.on("click", (e) => {
            // Same drawEnabledRef guard as the plain map click handler — a
            // polygon vertex landing on a biome must not also pick a point.
            if (drawEnabledRef.current) return;
            if (clickRef.current && e.latlng) {
              clickRef.current(Math.round(e.latlng.lat * 1e6) / 1e6,
                               Math.round(e.latlng.lng * 1e6) / 1e6);
            }
          });
        }
      },
    });

    if (!spec.label_property) return geoLayer;

    // A permanent on-map text label per polygon, sourced from spec.label_property
    // (e.g. the biome layer's natural_region field) — a SEPARATE marker layer
    // rather than a second bindTooltip, because Leaflet allows only one
    // tooltip per layer and the hover tooltip above already uses that slot
    // for the full property table. Centred on each polygon's own bounds:
    // several polygon fragments sharing the same region name each get their
    // own label, since the source geometry is genuinely split into that many
    // features (border simplification), not one label per unique name.
    const labels = [];
    geoLayer.eachLayer((featureLayer) => {
      if (!featureLayer.getBounds) return;
      const props = (featureLayer.feature && featureLayer.feature.properties) || {};
      const text = props[spec.label_property];
      if (!text) return;
      labels.push(L.marker(featureLayer.getBounds().getCenter(), {
        pane: "nmLabels",
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: "nm-vector-label",
          html: escapeHtml(String(text)),
          iconSize: null,
        }),
      }));
    });
    if (!labels.length) return geoLayer;

    const group = L.featureGroup([geoLayer, ...labels]);
    // Read by applyLabelVisibility below — kept on the layer itself rather
    // than in vectorRegistry, since the marker list is only known once the
    // layer is actually built.
    group._nmLabelMarkers = labels;
    group._nmLabelMinZoom = spec.label_min_zoom != null ? spec.label_min_zoom : 0;
    return group;
  };

  // Labels are built once (above) and never re-fetched; visibility is a pure
  // function of current zoom and the per-layer enabled flag, recomputed on
  // every map move/zoom (see the map-creation effect's onClipUpdate) and
  // once right after a layer is (re)built — cheap CSS display flips, not a
  // layer rebuild, so toggling "show labels" or panning/zooming never
  // touches the network or Earth Engine.
  const applyLabelVisibility = () => {
    const map = mapRef.current;
    if (!map) return;
    const zoom = map.getZoom();
    vectorRegistry.current.forEach((entry) => {
      const markers = entry.layer && entry.layer._nmLabelMarkers;
      if (!markers) return;
      const minZoom = entry.layer._nmLabelMinZoom || 0;
      const show = zoom >= minZoom;
      markers.forEach((m) => {
        const el = m.getElement && m.getElement();
        if (el) el.style.display = show ? "" : "none";
      });
    });
  };

  const specUrl = (spec, map) => {
    const url = new URL(spec.path, getBackendURL(env.PING));
    Object.entries(spec.query || {}).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v);
    });
    if (spec.dynamic && map) {
      const b = map.getBounds();
      // Rounded to 3 dp (~100 m) so that a one-pixel drag does not count as a
      // new viewport and refetch the same points.
      const r = (n) => Math.round(n * 1000) / 1000;
      url.searchParams.set("west", r(b.getWest()));
      url.searchParams.set("south", r(b.getSouth()));
      url.searchParams.set("east", r(b.getEast()));
      url.searchParams.set("north", r(b.getNorth()));
    }
    return url;
  };

  const syncDynamic = async () => {
    const map = mapRef.current;
    if (!map) return;
    const mod = await import("leaflet");
    const L = mod.default || mod;
    if (!mapRef.current) return;

    const registry = vectorRegistry.current;
    const incoming = (Array.isArray(vectorsRef.current) ? vectorsRef.current : [])
      .filter((s) => s.dynamic);

    for (const spec of incoming) {
      const tooFar = map.getZoom() < (spec.min_zoom || 0);
      const existing = registry.get(spec.id);
      if (tooFar) {
        if (existing) { map.removeLayer(existing.layer); registry.delete(spec.id); }
        dynamicKey.current.delete(spec.id);
        continue;
      }

      const url = specUrl(spec, map);
      const key = url.toString();
      if (dynamicKey.current.get(spec.id) === key) continue;
      dynamicKey.current.set(spec.id, key);

      try {
        const response = await fetch(key, {credentials: "omit"});
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        const data = await response.json();
        if (!mapRef.current) return;
        // Another move may have landed while this was in flight; its key is
        // already stored, so this response is stale and must not be drawn.
        if (dynamicKey.current.get(spec.id) !== key) continue;

        const previous = registry.get(spec.id);
        if (previous) map.removeLayer(previous.layer);
        const layer = buildLayer(L, spec, data);
        layer.addTo(map);
        registry.set(spec.id, {layer: layer, opacity: spec.opacity, dynamic: true});
        // Reported only for layers that ask for it, and only after the layer is
        // actually on the map - a state round-trip per pan for every dynamic
        // layer would undo the whole reason these are fetched over HTTP rather
        // than pushed through state.
        if (spec.emit_meta && layerMetaRef.current) {
          layerMetaRef.current({id: spec.id, ...((data && data.properties) || {})});
        }
      } catch (err) {
        console.error(`Dynamic layer ${spec.id} failed:`, err);
        dynamicKey.current.delete(spec.id);
      }
    }
  };

  useEffect(() => {
    let cancelled = false;

    const sync = async () => {
      const map = mapRef.current;
      if (!map || cancelled) return;

      const mod = await import("leaflet");
      const L = mod.default || mod;
      if (cancelled || !mapRef.current) return;

      if (!map.getPane("nmVectors")) {
        const pane = map.createPane("nmVectors");
        pane.style.zIndex = 350;
      }
      if (!map.getPane("nmLabels")) {
        // A SEPARATE pane, not just a higher z-index within nmVectors: with
        // preferCanvas, polygon fills paint onto one shared <canvas> per
        // pane rather than as ordinary stacked DOM children, so a label
        // <div> living in the same pane has no reliable way to stay above
        // that canvas — this is the same class of stacking surprise the
        // nmOverlays pane below already exists to avoid for hover events.
        const pane = map.createPane("nmLabels");
        pane.style.zIndex = 360;
        pane.style.pointerEvents = "none";
      }

      const registry = vectorRegistry.current;
      const incoming = Array.isArray(vectors) ? vectors : [];
      const wanted = new Set(incoming.map((spec) => spec.id));

      for (const [id, entry] of Array.from(registry.entries())) {
        if (!wanted.has(id)) {
          map.removeLayer(entry.layer);
          registry.delete(id);
          dynamicKey.current.delete(id);
        }
      }

      for (const spec of incoming) {
        if (spec.dynamic) continue;  // handled by syncDynamic, on map movement
        const existing = registry.get(spec.id);
        if (existing) {
          // Only the cheap properties can change; the geometry never does.
          if (existing.opacity !== spec.opacity) {
            existing.opacity = spec.opacity;
            existing.layer.setStyle((feature) => styleFor(spec, feature));
          }
          continue;
        }
        // A second render while the fetch is still in flight would start a
        // second fetch and add the layer twice.
        if (vectorPending.current.has(spec.id)) continue;
        vectorPending.current.add(spec.id);

        try {
          let data;
          if (spec.inline_data) {
            // Sent directly through state rather than fetched: a pasted point
            // list (state/_user_points.py) is session-specific, so there is no
            // shared backend path to fetch it from the way biomes/IFN have —
            // one dataset, everyone. The spec's id carries a version suffix
            // that changes on every submit/reset, so a new list is a NEW id
            // here (falls through to the "add" path below) rather than a
            // mutation of an existing, and-thus-considered-immutable, entry.
            data = spec.inline_data;
          } else {
            const url = specUrl(spec, null).toString();
            data = vectorData.current.get(url);
            if (!data) {
              const response = await fetch(url, {credentials: "omit"});
              if (!response.ok) {
                throw new Error(`${response.status} ${response.statusText}`);
              }
              data = await response.json();
              vectorData.current.set(url, data);
            }
          }
          if (cancelled || !mapRef.current) return;

          const layer = buildLayer(L, spec, data);
          layer.addTo(map);
          if (spec.attribution) {
            map.attributionControl.addAttribution(spec.attribution);
          }
          registry.set(spec.id, {layer: layer, opacity: spec.opacity});
          applyLabelVisibility();

          // Catch up with anything the user changed while the fetch was in
          // flight - see vectorsRef above.
          const latest = (Array.isArray(vectorsRef.current) ? vectorsRef.current
            : []).find((s) => s.id === spec.id);
          if (latest && latest.opacity !== spec.opacity) {
            registry.get(spec.id).opacity = latest.opacity;
            layer.setStyle((feature) => styleFor(latest, feature));
          }
        } catch (err) {
          console.error(`Vector layer ${spec.id} failed to load:`, err);
        } finally {
          vectorPending.current.delete(spec.id);
        }
      }

      // Filters or visibility may have changed under a dynamic layer without
      // the map moving at all, so the viewport pass has to run here too.
      syncDynamic();
    };

    if (readyRef.current) {
      sync();
    } else {
      const t = setInterval(() => {
        if (readyRef.current) {
          clearInterval(t);
          sync();
        }
      }, 50);
      return () => {
        cancelled = true;
        clearInterval(t);
      };
    }

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vectorKey]);

  // --- 3c. Refetch dynamic layers when the map settles --------------------
  // Bound once, on `moveend`/`zoomend` rather than `move`: a dragged map fires
  // dozens of `move` events a second, and each would be a request.
  useEffect(() => {
    const attach = () => {
      const map = mapRef.current;
      if (!map || map._nmDynamicBound) return false;
      const onSettle = () => {
        if (moveTimer.current) clearTimeout(moveTimer.current);
        moveTimer.current = setTimeout(syncDynamic, 200);
      };
      map.on("moveend zoomend", onSettle);
      map._nmDynamicBound = onSettle;
      return true;
    };

    if (attach()) return;
    const t = setInterval(() => { if (attach()) clearInterval(t); }, 50);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- 4b. Frame a selection ----------------------------------------------
  // `config.bounds` is initial framing and is deliberately never re-applied.
  // `config.fitBounds` is the opposite: Python sets it when the user narrows the
  // IFN filter to a state or a municipality, and the map flies there. Keyed on
  // the value, so re-rendering for an unrelated reason does not re-frame.
  const fitKey = JSON.stringify((config && config.fitBounds) || null);
  const lastFitRef = useRef(null);

  useEffect(() => {
    const apply = () => {
      const map = mapRef.current;
      if (!map) return;
      if (!config || !config.fitBounds) {
        // Python cleared the request. Forget what was last applied, so that
        // choosing the SAME filter again still re-frames - otherwise
        // "filter MT -> clear -> filter MT" leaves the map wherever it was.
        lastFitRef.current = null;
        return;
      }
      if (lastFitRef.current === fitKey) return;
      lastFitRef.current = fitKey;
      // maxZoom: a single conglomerado has a padded but still tiny box, and
      // without a ceiling fitBounds lands at z18 on imagery that has no detail
      // there - the user sees four grey tiles and assumes the layer broke.
      map.fitBounds(config.fitBounds, {padding: [24, 24], maxZoom: 12});
    };

    if (readyRef.current) {
      apply();
      return;
    }
    const t = setInterval(() => {
      if (readyRef.current) {
        clearInterval(t);
        apply();
      }
    }, 50);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);


  // --- 3d. Ctrl/Cmd-drag to select an area --------------------------------
  // Shift-drag is Leaflet's own box zoom and stays that way; taking it over
  // would cost a gesture people already use to frame a region before picking
  // points in it. Ctrl (Cmd on macOS) is free, and plain drag stays panning.
  //
  // Only armed while multiple selection is on, so the modifier does nothing
  // surprising the rest of the time.
  useEffect(() => {
    const attach = () => {
      const map = mapRef.current;
      if (!map || map._nmAreaBound) return false;

      const container = map.getContainer();
      let start = null;
      let box = null;

      const cleanup = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (box) { box.remove(); box = null; }
        start = null;
        map.dragging.enable();
      };

      const onMove = (e) => {
        if (!start || !box) return;
        const p = map.mouseEventToContainerPoint(e);
        box.style.left = `${Math.min(start.x, p.x)}px`;
        box.style.top = `${Math.min(start.y, p.y)}px`;
        box.style.width = `${Math.abs(p.x - start.x)}px`;
        box.style.height = `${Math.abs(p.y - start.y)}px`;
      };

      const onUp = (e) => {
        if (!start) { cleanup(); return; }
        const end = map.mouseEventToContainerPoint(e);
        const dragged = Math.abs(end.x - start.x) > 4 &&
                        Math.abs(end.y - start.y) > 4;
        const from = start;
        cleanup();
        if (!dragged) return;

        const a = map.containerPointToLatLng(from);
        const b = map.containerPointToLatLng(end);
        // The mouseup is followed by a click on the container; without this the
        // map would also try to drop a study point where the drag ended.
        pointClickAt.current = Date.now();
        if (areaRef.current) {
          areaRef.current({
            west: Math.min(a.lng, b.lng), east: Math.max(a.lng, b.lng),
            south: Math.min(a.lat, b.lat), north: Math.max(a.lat, b.lat),
          });
        }
      };

      const onDown = (e) => {
        if (!areaEnabledRef.current) return;
        if (e.button !== 0 || !(e.ctrlKey || e.metaKey)) return;
        e.preventDefault();
        map.dragging.disable();
        start = map.mouseEventToContainerPoint(e);
        box = document.createElement("div");
        box.className = "nm-area-box";
        box.style.cssText = [
          "position:absolute", "border:2px dashed #ff8a00",
          "background:rgba(255,138,0,.15)", "z-index:750",
          "pointer-events:none", "left:0", "top:0", "width:0", "height:0",
        ].join(";");
        container.appendChild(box);
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      };

      // On macOS ctrl+click is the context-menu gesture; without this the menu
      // opens on top of the box the user is dragging.
      const onContextMenu = (e) => {
        if (areaEnabledRef.current && (e.ctrlKey || e.metaKey)) e.preventDefault();
      };

      container.addEventListener("mousedown", onDown);
      container.addEventListener("contextmenu", onContextMenu);
      map._nmAreaBound = {onDown, onContextMenu};
      return true;
    };

    if (attach()) return;
    const t = setInterval(() => { if (attach()) clearInterval(t); }, 50);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- 4. Follow programmatic view changes from Python ---------------------
  // Only when Python actually asks for a DIFFERENT view. Comparing against the
  // map's current position instead would re-centre on every unrelated config
  // change - toggling the swipe divider, for instance - yanking the user back
  // to the default framing and breaking the "viewport is never disturbed"
  // guarantee this component exists to provide.
  //
  // Bounds are initial framing only and are deliberately not re-applied here.
  const lastViewRef = useRef(null);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !config || !config.center) return;

    const desired = JSON.stringify([config.center, config.zoom]);
    if (lastViewRef.current === null) {
      // First run: the map was already framed at construction.
      lastViewRef.current = desired;
      return;
    }
    if (lastViewRef.current === desired) return;

    lastViewRef.current = desired;
    map.setView(config.center, config.zoom);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(config)]);
}

// Style one feature of a vector layer from its spec's palette.
//
// The stroke is the palette colour at full strength and the fill is the same
// colour at the layer's opacity: one hue per biome, so the legend, the fill and
// the outline cannot drift apart.
function styleFor(spec, feature) {
  const props = (feature && feature.properties) || {};
  const key = props[spec.color_property];
  const palette = spec.palette || {};
  const color = palette[key] || spec.default_color || "9e9e9e";
  return {
    color: `#${color}`,
    weight: spec.weight != null ? spec.weight : 1,
    opacity: 0.9,
    fill: true,
    fillColor: `#${color}`,
    // Never 0: with preferCanvas the renderer still hit-tests a zero-opacity
    // fill, but a reader cannot tell the layer is on.
    fillOpacity: spec.opacity != null ? spec.opacity : 0.4,
  };
}

// The fill colour one feature takes from its spec's palette, or {} when the
// spec does not colour per feature.
//
// Split out from pointStyleFor because the hover style has to re-apply exactly
// this and nothing else: a hover_style that carried its own fillColor would
// override the palette, and one that did not would fall back to whatever
// circleMarker defaults to.
function paletteFill(spec, feature) {
  if (!spec.color_property) return {};
  const props = (feature && feature.properties) || {};
  const palette = spec.palette || {};
  const color = palette[props[spec.color_property]] || spec.default_color;
  return color ? {fillColor: `#${color}`} : {};
}

// A point layer's per-feature style: the spec's flat point_style with the
// palette colour merged over it.
//
// Until the GBIF layer every point layer here (embargos, autos de infração,
// IFN conglomerados, pasted points) drew in one flat colour, so point_style
// alone was the whole style and styleFor's palette handling was reachable only
// by polygons. Colouring occurrences by kingdom needs both at once — the
// radius/stroke from point_style, the fill from the palette — which is the one
// combination the two branches could not previously express.
function pointStyleFor(spec, feature) {
  return {...(spec.point_style || {}), ...paletteFill(spec, feature)};
}

// Build the hover tooltip from the spec's label/property pairs.
// Properties that are missing or empty are skipped rather than rendered as an
// empty row - several IBGE polygons have no natural-region name.
// Word-wraps at ~width characters per line rather than leaving it to CSS:
// a long domain/region name left to `overflow-wrap` stretches the tooltip
// out to its max-width before wrapping at all, which is what made the box
// feel inconsistently sized from one feature to the next. Breaking at word
// boundaries near `width` keeps every tooltip roughly the same, compact
// shape regardless of content length.
function wrapWords(text, width) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (line && candidate.length > width) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

// Property titles are short (1-3 words) but still crowd the label column at
// its fixed width — breaking after the first word gives a predictable two
// lines ("Domínio" / "fitogeográfico") without needing a width heuristic
// tuned for prose, which wrapWords is built for.
function splitLabel(text) {
  const words = String(text).split(/\s+/).filter(Boolean);
  return words.length <= 1 ? [String(text)] : [words[0], words.slice(1).join(" ")];
}

function tooltipHtml(spec, feature) {
  const props = (feature && feature.properties) || {};
  // Values already shown, so the same string is never printed twice in one
  // tooltip. Two unrelated causes produce that, and both look like a bug to a
  // reader:
  //   * Legitimately, when a record is only determined to family or genus
  //     level, GBIF sets the interpreted scientificName TO that family or
  //     genus - so "Nome científico: Eriocaulaceae / Família: Eriocaulaceae"
  //     is correct, and still reads as a mistake.
  //   * Not legitimately, when a publisher's mapping to GBIF has packed the
  //     same content into many fields at once. services/gbif.py drops the
  //     worst of those on the way through; this catches what survives.
  // First label wins, which is the spec's own ordering - the most specific
  // reading of the value is listed first in every tooltip here.
  const seen = new Set();
  const rows = (spec.tooltip || [])
    .map((entry) => {
      const value = props[entry.property];
      if (value === undefined || value === null || value === "") return null;
      const key = String(value);
      if (seen.has(key)) return null;
      seen.add(key);
      const labelHtml = splitLabel(entry.label).map(escapeHtml).join("<br>");
      let valueHtml;
      // https:// only: this value is server-built (see e.g. services/gbif.py's
      // gbif_url), but it still lands in innerHTML, so a stray non-http(s)
      // scheme (a would-be `javascript:`) falls back to plain escaped text
      // instead of becoming a clickable anchor.
      if (entry.link && /^https:\/\//.test(String(value))) {
        // Inert in the hover tooltip (pointer-events: none there) and only
        // actually clickable once a click has pinned this as a popup — see
        // buildLayer's bindPopup.
        const text = escapeHtml(entry.link_text || String(value));
        valueHtml = `<a href="${escapeHtml(value)}" target="_blank" rel="noopener noreferrer">${text}</a>`;
      } else {
        valueHtml = wrapWords(value, 25).map(escapeHtml).join("<br>");
      }
      return `<div class="nm-tip-row"><span class="nm-tip-label">${labelHtml}</span><span class="nm-tip-value">${valueHtml}</span></div>`;
    })
    .filter(Boolean);
  if (!rows.length) return null;
  if (spec.offer_select) {
    // A plain map click recentres the study area immediately; this layer's
    // own click instead pins the record open (see attachPointHandlers), and
    // offers the recentre as a deliberate action inside it — the button is
    // wired up in buildLayer's popupopen handler, which is the one place
    // that still has this feature's own coordinates in closure.
    rows.unshift(`<button type="button" class="nm-tip-select-btn">${escapeHtml(spec.select_label || "New study area")}</button>`);
  }
  return rows.join("");
}

// The tooltip is built as an HTML string, and these values come from a data
// file rather than from code, so they are escaped before insertion.
function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
