/**
 * What is the runner doing *right now*?
 *
 * The server only speaks when a new GPS fix arrives. Silence is information
 * too ("no signal", "stopped"), so the live status is derived on the client
 * from the last snapshot and the current time.
 */
import type { Snapshot } from "../api/types";

export type LiveStatus =
  | "waiting" // session started, no position received yet
  | "moving"
  | "stopped" // fixes keep coming but the runner stays in place
  | "no_signal" // no fix for a while: we only know the last position
  | "finished" // arrived
  | "ended"; // runner stopped sharing

/** No fix for this long means we lost contact with the runner's phone. */
export const NO_SIGNAL_AFTER_S = 120;
/** Fixes arriving but no movement for this long means "stopped". */
export const STOPPED_AFTER_S = 75;

const ms = (iso: string) => new Date(iso).getTime();

export function deriveStatus(snapshot: Snapshot, nowMs: number): LiveStatus {
  if (snapshot.state === "ended") return "ended";
  if (snapshot.state === "finished") return "finished";
  if (!snapshot.position) return "waiting";
  if (nowMs - ms(snapshot.position.ts) > NO_SIGNAL_AFTER_S * 1000) return "no_signal";
  if (snapshot.last_moved_at && nowMs - ms(snapshot.last_moved_at) > STOPPED_AFTER_S * 1000) {
    return "stopped";
  }
  return "moving";
}

/**
 * Expected arrival time (epoch ms), or null when there is no estimate.
 *
 * The ETA is "moving time left". While the runner moves (or we lost signal
 * and assume they still do) the arrival time is fixed and the countdown
 * runs. While they are stopped the countdown freezes and the arrival time
 * slides later.
 */
export function arrivalTimeMs(snapshot: Snapshot, status: LiveStatus, nowMs: number): number | null {
  if (!snapshot.eta || status === "waiting" || status === "ended") return null;
  if (status === "finished") return snapshot.arrived_at ? ms(snapshot.arrived_at) : nowMs;
  const remainingMs = snapshot.eta.seconds * 1000;
  if (status === "stopped") return nowMs + remainingMs;
  return Math.max(nowMs, ms(snapshot.eta.computed_at) + remainingMs);
}

/** Seconds since the runner last moved, or null if never seen moving. */
export function secondsSinceMoved(snapshot: Snapshot, nowMs: number): number | null {
  return snapshot.last_moved_at ? Math.max(0, (nowMs - ms(snapshot.last_moved_at)) / 1000) : null;
}

/** Seconds since the last GPS fix, or null if there is none. */
export function secondsSinceFix(snapshot: Snapshot, nowMs: number): number | null {
  return snapshot.position ? Math.max(0, (nowMs - ms(snapshot.position.ts)) / 1000) : null;
}
