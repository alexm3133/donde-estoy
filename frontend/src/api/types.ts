/** Shapes of the backend API (mirrors backend/app/schemas.py). */

export type Activity = "run" | "hike";
export type SessionState = "active" | "finished" | "ended";
export type Confidence = "low" | "medium" | "high";

/** `[lat, lon, elevation | null]` */
export type RoutePoint = [number, number, number | null];
/** `[lat, lon, elevation, distanceFromStart]` */
export type RouteVertex = [number, number, number, number];

export interface LatLon {
  lat: number;
  lon: number;
}

export interface Position extends LatLon {
  ele: number | null;
  accuracy: number | null;
  /** ISO timestamp */
  ts: string;
}

export interface Progress {
  done_m: number | null;
  total_m: number | null;
  remaining_m: number;
  remaining_ascent_m: number;
  remaining_descent_m: number;
  off_route: boolean;
}

export interface Eta {
  /** Moving seconds left, as of `computed_at`. */
  seconds: number;
  low_seconds: number;
  high_seconds: number;
  confidence: Confidence;
  computed_at: string;
}

export interface Snapshot {
  runner_name: string;
  activity: Activity;
  state: SessionState;
  server_time: string;
  created_at: string;
  expires_at: string;
  stall_alert_minutes: number;
  destination: LatLon | null;
  has_route: boolean;
  position: Position | null;
  started_at: string | null;
  last_moved_at: string | null;
  arrived_at: string | null;
  progress: Progress | null;
  eta: Eta | null;
  stats: { moving_time_s: number; distance_m: number };
}

export interface Route {
  points: RouteVertex[];
  distance_m: number;
  ascent_m: number;
  descent_m: number;
  has_elevation: boolean;
}

export interface SessionView extends Snapshot {
  route: Route | null;
  track: [number, number][];
}

export interface ParsedRoute extends Route {
  name: string | null;
  raw_points: RoutePoint[];
}

export interface SessionCreate {
  runner_name: string;
  activity: Activity;
  stall_alert_minutes: number;
  duration_hours?: number;
  destination?: LatLon;
  route_points?: RoutePoint[];
}

export interface SessionCreated {
  id: string;
  runner_token: string;
  view_token: string;
  share_url: string;
  expires_at: string;
  snapshot: Snapshot;
}

export interface PositionIn extends LatLon {
  ele?: number | null;
  accuracy?: number | null;
  ts: string;
}

export type LiveMessage =
  | { type: "snapshot"; data: Snapshot }
  | { type: "ping" }
  | { type: "expired" };
