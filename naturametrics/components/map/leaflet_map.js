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

function useNaturametricsMap(containerRef, config, layers, overlays, vectors, onMapClick) {
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
  const overlayRef = useRef(null);
  const clickRef = useRef(onMapClick);
  const readyRef = useRef(false);

  // Keep the click callback current without re-registering the Leaflet handler.
  clickRef.current = onMapClick;
  vectorsRef.current = vectors;

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
        if (clickRef.current) {
          clickRef.current(
            Math.round(e.latlng.lat * 1e6) / 1e6,
            Math.round(e.latlng.lng * 1e6) / 1e6
          );
        }
      });

      mapRef.current = map;
      readyRef.current = true;

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
        if (containerRef.current) containerRef.current._nmMap = null;
        map.remove();
        mapRef.current = null;
        overlayRef.current = null;
        readyRef.current = false;
        layerRegistry.current.clear();
        vectorRegistry.current.clear();
        vectorPending.current.clear();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      el.style.clipPath = "";
      if (entry.clip === "left") {
        el.style.clip = `rect(${nw.y}px, ${splitX}px, ${se.y}px, ${nw.x}px)`;
      } else if (entry.clip === "right") {
        el.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${splitX}px)`;
      } else {
        el.style.clip = "";
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
  const overlayKey = JSON.stringify(overlays);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const map = mapRef.current;
      if (!map) return;
      const mod = await import("leaflet");
      const L = mod.default || mod;
      if (cancelled || !mapRef.current) return;

      if (overlayRef.current) {
        map.removeLayer(overlayRef.current);
        overlayRef.current = null;
      }
      if (!overlays || !overlays.features || !overlays.features.length) return;

      const group = L.geoJSON(overlays, {
        // Buffer outlines must never swallow map clicks - the user has to be
        // able to click a new study point straight through them.
        interactive: false,
        style: (feature) => {
          const props = feature.properties || {};
          if (props.role !== "buffer") return {};
          return {
            color: "#ffffff",
            weight: 2,
            opacity: 0.95,
            fill: false,
            dashArray: props.radius_km <= 1 ? null : "5,4",
          };
        },
        pointToLayer: (feature, latlng) =>
          L.circleMarker(latlng, {
            radius: 6,
            color: "#ffffff",
            weight: 2,
            fillColor: "#e5484d",
            fillOpacity: 1,
            interactive: false,
          }),
      });
      group.addTo(map);
      overlayRef.current = group;
    })();

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlayKey]);


  // --- 3b. Browser-side vector layers -------------------------------------
  // Tiles cannot answer "what is under the cursor" - they are pixels. A layer
  // that has to name itself on hover therefore needs real geometry in the
  // browser, so these specs carry a PATH and the hook fetches the GeoJSON over
  // plain HTTP (cacheable, gzipped, and off the WebSocket - see
  // naturametrics/api/__init__.py).
  //
  // They live in their own pane between the tiles (200) and the overlay pane
  // (400): above the imagery they contextualise, below the study point and its
  // buffers, which must never be obscured.
  const vectorKey = JSON.stringify(vectors);

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

      const registry = vectorRegistry.current;
      const incoming = Array.isArray(vectors) ? vectors : [];
      const wanted = new Set(incoming.map((spec) => spec.id));

      for (const [id, entry] of Array.from(registry.entries())) {
        if (!wanted.has(id)) {
          map.removeLayer(entry.layer);
          registry.delete(id);
        }
      }

      for (const spec of incoming) {
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
          const url = new URL(spec.path, getBackendURL(env.PING)).href;
          let data = vectorData.current.get(url);
          if (!data) {
            const response = await fetch(url, {credentials: "omit"});
            if (!response.ok) {
              throw new Error(`${response.status} ${response.statusText}`);
            }
            data = await response.json();
            vectorData.current.set(url, data);
          }
          if (cancelled || !mapRef.current) return;

          const layer = L.geoJSON(data, {
            pane: "nmVectors",
            style: (feature) => styleFor(spec, feature),
            onEachFeature: (feature, featureLayer) => {
              const html = tooltipHtml(spec, feature);
              if (html) {
                // sticky: the tooltip follows the cursor inside the polygon,
                // which is the only sane behaviour for shapes the size of the
                // Amazon - anchored to the centroid it would be off-screen.
                featureLayer.bindTooltip(html, {
                  sticky: true,
                  direction: "top",
                  opacity: 0.95,
                  className: "nm-vector-tip",
                });
              }
              // An interactive polygon swallows the click that would otherwise
              // reach the map, so the study-point selection has to be forwarded
              // explicitly or clicking anywhere on a biome does nothing.
              featureLayer.on("click", (e) => {
                if (clickRef.current && e.latlng) {
                  clickRef.current(
                    Math.round(e.latlng.lat * 1e6) / 1e6,
                    Math.round(e.latlng.lng * 1e6) / 1e6
                  );
                }
              });
            },
          });
          layer.addTo(map);
          if (spec.attribution) {
            map.attributionControl.addAttribution(spec.attribution);
          }
          registry.set(spec.id, {layer: layer, opacity: spec.opacity});

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

// Build the hover tooltip from the spec's label/property pairs.
// Properties that are missing or empty are skipped rather than rendered as an
// empty row - several IBGE polygons have no natural-region name.
function tooltipHtml(spec, feature) {
  const props = (feature && feature.properties) || {};
  const rows = (spec.tooltip || [])
    .map((entry) => {
      const value = props[entry.property];
      if (value === undefined || value === null || value === "") return null;
      return `<div class="nm-tip-row"><span class="nm-tip-label">${escapeHtml(
        entry.label
      )}</span><span class="nm-tip-value">${escapeHtml(String(value))}</span></div>`;
    })
    .filter(Boolean);
  return rows.length ? rows.join("") : null;
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
