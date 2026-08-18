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

function useNaturametricsMap(containerRef, config, layers, overlays, onMapClick) {
  const mapRef = useRef(null);
  const layerRegistry = useRef(new Map());
  const overlayRef = useRef(null);
  const clickRef = useRef(onMapClick);
  const readyRef = useRef(false);

  // Keep the click callback current without re-registering the Leaflet handler.
  clickRef.current = onMapClick;

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
        });
      });
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

  // --- 4. Follow programmatic view changes from Python ---------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !config || !config.center) return;
    // Bounds are an initial framing only; re-fitting on every config change
    // would fight the user's own pan and zoom.
    const current = map.getCenter();
    const moved =
      Math.abs(current.lat - config.center[0]) > 1e-6 ||
      Math.abs(current.lng - config.center[1]) > 1e-6 ||
      map.getZoom() !== config.zoom;
    if (moved) {
      map.setView(config.center, config.zoom);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(config)]);
}
