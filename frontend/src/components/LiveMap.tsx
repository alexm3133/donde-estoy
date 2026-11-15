/**
 * The topographic map: route, where the runner has been, where they are now
 * and where they are going. A thin React wrapper around MapLibre GL.
 */
import { IonIcon } from "@ionic/react";
import { locate } from "ionicons/icons";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useCallback, useEffect, useRef, useState } from "react";
import type { LatLon, RouteVertex } from "../api/types";
import { token, useTheme } from "../theme/theme";
import "./LiveMap.css";
import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  TILE_ATTRIBUTION,
  TILE_MAX_ZOOM,
  TILE_URLS,
} from "./mapConfig";

export type MarkerTone = "moving" | "stopped" | "lost" | "done";

export interface MapPadding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

interface LiveMapProps {
  route?: RouteVertex[] | null;
  /** Distance already covered along the route (greys out that part). */
  progressM?: number | null;
  /** Path actually travelled, `[lat, lon]` pairs. */
  track?: [number, number][];
  position?: LatLon | null;
  destination?: LatLon | null;
  markerTone?: MarkerTone;
  /** Screen area hidden behind overlay cards; the camera keeps clear of it. */
  padding?: MapPadding;
  /** When set, tapping the map reports the tapped point (destination picker). */
  onPick?: (point: LatLon) => void;
  /** Accessible name of the map region and of the re-centre button. */
  label: string;
  recenterLabel: string;
}

const NO_PADDING: MapPadding = { top: 0, right: 0, bottom: 0, left: 0 };
interface LineFeature {
  type: "Feature";
  properties: Record<string, never>;
  geometry: { type: "LineString"; coordinates: [number, number][] };
}

const EMPTY_LINE: LineFeature = {
  type: "Feature",
  properties: {},
  geometry: { type: "LineString", coordinates: [] },
};

function line(coordinates: [number, number][]): LineFeature {
  return { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates } };
}

/** `[lon, lat]` coordinates of the route up to `progressM`. */
function coveredPart(route: RouteVertex[], progressM: number): [number, number][] {
  const covered: [number, number][] = [];
  for (let i = 0; i < route.length; i++) {
    const [lat, lon, , distance] = route[i];
    if (distance <= progressM) {
      covered.push([lon, lat]);
      continue;
    }
    if (i > 0) {
      const [prevLat, prevLon, , prevDistance] = route[i - 1];
      const t = (progressM - prevDistance) / (distance - prevDistance || 1);
      covered.push([prevLon + t * (lon - prevLon), prevLat + t * (lat - prevLat)]);
    }
    break;
  }
  return covered;
}

function markerElement(className: string, html: string): HTMLDivElement {
  const element = document.createElement("div");
  element.className = className;
  element.innerHTML = html;
  element.setAttribute("aria-hidden", "true"); // described in text elsewhere
  return element;
}

export function LiveMap({
  route,
  progressM,
  track,
  position,
  destination,
  markerTone = "moving",
  padding = NO_PADDING,
  onPick,
  label,
  recenterLabel,
}: LiveMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const runnerMarker = useRef<maplibregl.Marker | null>(null);
  const destinationMarker = useRef<maplibregl.Marker | null>(null);
  const [ready, setReady] = useState(false);
  /** The camera follows the runner until the user moves the map by hand. */
  const [following, setFollowing] = useState(true);
  const hasFramed = useRef(false);
  const theme = useTheme();

  // Latest props for use inside map event handlers.
  const latest = useRef({ route, position, destination, padding, onPick });
  latest.current = { route, position, destination, padding, onPick };

  // ---- create the map once -------------------------------------------
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      center: [DEFAULT_CENTER.lon, DEFAULT_CENTER.lat],
      zoom: DEFAULT_ZOOM,
      maxZoom: TILE_MAX_ZOOM,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      style: {
        version: 8,
        sources: {
          topo: {
            type: "raster",
            tiles: TILE_URLS,
            tileSize: 256,
            maxzoom: TILE_MAX_ZOOM,
            attribution: TILE_ATTRIBUTION,
          },
          route: { type: "geojson", data: EMPTY_LINE },
          "route-done": { type: "geojson", data: EMPTY_LINE },
          track: { type: "geojson", data: EMPTY_LINE },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": token("--de-bg") } },
          { id: "topo", type: "raster", source: "topo" },
          {
            id: "route-casing",
            type: "line",
            source: "route",
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": token("--de-route-casing"), "line-width": 8, "line-opacity": 0.85 },
          },
          {
            id: "route",
            type: "line",
            source: "route",
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": token("--de-route"), "line-width": 4.5 },
          },
          {
            id: "route-done",
            type: "line",
            source: "route-done",
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": token("--de-route-done"), "line-width": 4.5 },
          },
          {
            id: "track",
            type: "line",
            source: "track",
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": token("--de-track"), "line-width": 3, "line-dasharray": [0.2, 2] },
          },
        ],
      },
    });
    map.touchZoomRotate.disableRotation();
    // Attribution stays visible (tile licence); compact keeps it out of the way.
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "top-right");
    map.on("load", () => setReady(true));
    // Only gestures made by a person switch off "follow the runner".
    map.on("dragstart", (event) => {
      if (event.originalEvent) setFollowing(false);
    });
    map.on("click", (event) => {
      latest.current.onPick?.({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    });
    mapRef.current = map;

    // Keep the canvas in sync when the layout changes (rotation, panels).
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container.current);

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
      runnerMarker.current = null;
      destinationMarker.current = null;
    };
  }, []);

  // ---- theme ------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const dark = theme === "dark";
    // Topo tiles are paper-white: tone them down at night to avoid glare
    // while keeping contour lines and labels readable.
    map.setPaintProperty("topo", "raster-brightness-max", dark ? 0.78 : 1);
    map.setPaintProperty("topo", "raster-saturation", dark ? -0.3 : 0);
    map.setPaintProperty("topo", "raster-contrast", dark ? 0.12 : 0);
    map.setPaintProperty("background", "background-color", token("--de-bg"));
    map.setPaintProperty("route-casing", "line-color", token("--de-route-casing"));
    map.setPaintProperty("route", "line-color", token("--de-route"));
    map.setPaintProperty("route-done", "line-color", token("--de-route-done"));
    map.setPaintProperty("track", "line-color", token("--de-track"));
  }, [theme, ready]);

  // ---- lines ------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource;
    source("route").setData(route ? line(route.map(([lat, lon]) => [lon, lat])) : EMPTY_LINE);
    source("route-done").setData(
      route && progressM ? line(coveredPart(route, progressM)) : EMPTY_LINE,
    );
    source("track").setData(track ? line(track.map(([lat, lon]) => [lon, lat])) : EMPTY_LINE);
  }, [route, progressM, track, ready]);

  // ---- markers ------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (!destination) {
      destinationMarker.current?.remove();
      destinationMarker.current = null;
    } else {
      destinationMarker.current ??= new maplibregl.Marker({
        element: markerElement(
          "de-flag",
          '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M6 3v18M6 4h11l-2.5 4L17 12H6" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        ),
        anchor: "bottom-left",
      })
        .setLngLat([destination.lon, destination.lat])
        .addTo(map);
      destinationMarker.current.setLngLat([destination.lon, destination.lat]);
    }
  }, [destination, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (!position) {
      runnerMarker.current?.remove();
      runnerMarker.current = null;
      return;
    }
    runnerMarker.current ??= new maplibregl.Marker({
      element: markerElement(
        "de-runner",
        '<span class="de-runner__pulse"></span><span class="de-runner__dot"></span>',
      ),
    })
      .setLngLat([position.lon, position.lat])
      .addTo(map);
    runnerMarker.current.setLngLat([position.lon, position.lat]);
    runnerMarker.current.getElement().dataset.tone = markerTone;
  }, [position, markerTone, ready]);

  // ---- camera ------------------------------------------------------------
  const cameraPadding = useCallback((margin: number) => {
    const p = latest.current.padding;
    return {
      top: p.top + margin,
      right: p.right + margin,
      bottom: p.bottom + margin,
      left: p.left + margin,
    };
  }, []);

  /** Show everything that matters: runner, destination and the route. */
  const frame = useCallback(
    (animate: boolean) => {
      const map = mapRef.current;
      const { route: r, position: p, destination: d } = latest.current;
      if (!map) return false;
      const bounds = new maplibregl.LngLatBounds();
      r?.forEach(([lat, lon]) => bounds.extend([lon, lat]));
      if (p) bounds.extend([p.lon, p.lat]);
      if (d) bounds.extend([d.lon, d.lat]);
      if (bounds.isEmpty()) return false;
      map.fitBounds(bounds, {
        padding: cameraPadding(56),
        maxZoom: 15.5,
        duration: animate ? 700 : 0,
      });
      return true;
    },
    [cameraPadding],
  );

  // First time there is something to show: frame it.
  useEffect(() => {
    if (!ready || hasFramed.current) return;
    hasFramed.current = frame(false);
  }, [ready, route, position, destination, frame]);

  // A destination picked by hand (or a new route) deserves a fresh frame.
  const routeKey = route ? `${route.length}:${route[0][0]}:${route[0][1]}` : "";
  useEffect(() => {
    if (ready && hasFramed.current && routeKey) frame(true);
  }, [routeKey, ready, frame]);

  // The cards over the map changed size (e.g. an alert appeared): re-frame
  // so the runner does not end up hidden behind them.
  const paddingKey = `${padding.top}:${padding.right}:${padding.bottom}:${padding.left}`;
  useEffect(() => {
    if (ready && hasFramed.current && following) frame(false);
    // `following` is read, not watched: resuming follow already re-frames.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paddingKey, ready, frame]);

  // While following, pan when the runner gets close to the edge of the
  // visible area (the part not covered by cards).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !following || !position || !hasFramed.current) return;
    const point = map.project([position.lon, position.lat]);
    const pad = cameraPadding(48);
    const canvas = map.getCanvas();
    const inside =
      point.x > pad.left &&
      point.x < canvas.clientWidth - pad.right &&
      point.y > pad.top &&
      point.y < canvas.clientHeight - pad.bottom;
    if (!inside) {
      map.easeTo({
        center: [position.lon, position.lat],
        padding: cameraPadding(0),
        duration: 900,
      });
    }
  }, [position, following, ready, cameraPadding]);

  const recenter = () => {
    setFollowing(true);
    frame(true);
  };

  return (
    <div className={`de-map${onPick ? " de-map--pick" : ""}`}>
      <div ref={container} className="de-map__canvas" role="application" aria-label={label} />
      {!following && (
        <button
          type="button"
          className="de-icon-btn de-glass de-map__recenter"
          style={{ bottom: padding.bottom + 16, right: padding.right + 16 }}
          onClick={recenter}
          aria-label={recenterLabel}
          title={recenterLabel}
        >
          <IonIcon icon={locate} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
