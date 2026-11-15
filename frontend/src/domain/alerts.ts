/**
 * Viewer alerts: "arriving soon", "has arrived" and the safety alert
 * ("hasn't moved for X minutes").
 *
 * Pure logic: given the snapshot, the derived status, the time and what has
 * already been announced, decide what to show and what to announce now.
 */
import type { Snapshot } from "../api/types";
import { arrivalTimeMs, type LiveStatus, secondsSinceMoved } from "./status";

export type AlertKind = "arriving_soon" | "arrived" | "stalled";

/** "Arriving soon" fires when the ETA drops to this... */
export const ARRIVING_SOON_S = 15 * 60;
/** ...and may fire again only after the ETA went back above this. */
export const ARRIVING_SOON_REARM_S = 20 * 60;

/** What has been announced so far (persisted per link by the caller). */
export interface AlertMemory {
  arrivingSoon: boolean;
  arrived: boolean;
  stalled: boolean;
  /** We have seen this session while the runner was still on the way. */
  sawActive: boolean;
}

export const NO_ALERTS: AlertMemory = {
  arrivingSoon: false,
  arrived: false,
  stalled: false,
  sawActive: false,
};

export interface AlertEvaluation {
  /** The condition to keep on screen right now (most urgent one). */
  active: AlertKind | null;
  /** Conditions that just started and deserve a sound / notification. */
  fire: AlertKind[];
  memory: AlertMemory;
}

export function evaluateAlerts(
  snapshot: Snapshot,
  status: LiveStatus,
  nowMs: number,
  previous: AlertMemory,
): AlertEvaluation {
  const memory = { ...previous };
  const fire: AlertKind[] = [];
  const onTheWay = status === "moving" || status === "stopped" || status === "no_signal";

  // --- has arrived ----------------------------------------------------
  if (status === "finished") {
    // Announce only if we were watching; opening an old link stays quiet.
    if (!memory.arrived && memory.sawActive) fire.push("arrived");
    memory.arrived = true;
    return { active: "arrived", fire, memory };
  }
  if (!onTheWay) return { active: null, fire, memory };
  memory.sawActive = true;

  // --- safety: not moving for too long --------------------------------
  const still = secondsSinceMoved(snapshot, nowMs);
  const stalled = still !== null && still >= snapshot.stall_alert_minutes * 60;
  if (stalled && !memory.stalled) fire.push("stalled");
  memory.stalled = stalled; // re-arms as soon as the runner moves again

  // --- arriving soon --------------------------------------------------
  const arrival = arrivalTimeMs(snapshot, status, nowMs);
  const secondsLeft = arrival === null ? null : (arrival - nowMs) / 1000;
  const soon = secondsLeft !== null && secondsLeft <= ARRIVING_SOON_S;
  if (soon && !memory.arrivingSoon && !stalled) {
    fire.push("arriving_soon");
    memory.arrivingSoon = true;
  } else if (secondsLeft !== null && secondsLeft > ARRIVING_SOON_REARM_S) {
    memory.arrivingSoon = false;
  }

  return { active: stalled ? "stalled" : soon ? "arriving_soon" : null, fire, memory };
}
