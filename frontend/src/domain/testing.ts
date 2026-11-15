/** Test helper: a snapshot of a runner on the way, with overridable fields. */
import type { Snapshot } from "../api/types";

export const T0 = Date.parse("2026-06-01T10:00:00Z");
export const iso = (ms: number) => new Date(ms).toISOString();

export function snapshot(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    runner_name: "Alex",
    activity: "run",
    state: "active",
    server_time: iso(T0),
    created_at: iso(T0 - 3_600_000),
    expires_at: iso(T0 + 3_600_000),
    stall_alert_minutes: 10,
    destination: { lat: 42.1, lon: 1.6 },
    has_route: true,
    position: { lat: 42, lon: 1.5, ele: 1200, accuracy: 8, ts: iso(T0) },
    started_at: iso(T0 - 1_800_000),
    last_moved_at: iso(T0),
    arrived_at: null,
    progress: {
      done_m: 4000,
      total_m: 10_000,
      remaining_m: 6000,
      remaining_ascent_m: 300,
      remaining_descent_m: 500,
      off_route: false,
    },
    eta: {
      seconds: 40 * 60,
      low_seconds: 36 * 60,
      high_seconds: 44 * 60,
      confidence: "high",
      computed_at: iso(T0),
    },
    stats: { moving_time_s: 1700, distance_m: 4000 },
    ...overrides,
  };
}
