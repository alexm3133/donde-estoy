import { describe, expect, it } from "vitest";
import type { Snapshot } from "../api/types";
import { type AlertMemory, evaluateAlerts, NO_ALERTS } from "./alerts";
import { deriveStatus } from "./status";
import { iso, snapshot, T0 } from "./testing";

const MIN = 60_000;

/** Run the evaluator the way the viewer page does: derive status, keep memory. */
function watch(memory: AlertMemory, snap: Snapshot, now: number) {
  return evaluateAlerts(snap, deriveStatus(snap, now), now, memory);
}

const withEta = (minutes: number, at = T0) =>
  snapshot({
    position: { ...snapshot().position!, ts: iso(at) },
    last_moved_at: iso(at),
    eta: { ...snapshot().eta!, seconds: minutes * 60, computed_at: iso(at) },
  });

describe("arriving soon", () => {
  it("fires once when the ETA drops to 15 minutes", () => {
    let result = watch(NO_ALERTS, withEta(40), T0);
    expect(result.fire).toEqual([]);
    expect(result.active).toBeNull();

    result = watch(result.memory, withEta(14, T0 + 26 * MIN), T0 + 26 * MIN);
    expect(result.fire).toEqual(["arriving_soon"]);
    expect(result.active).toBe("arriving_soon");

    result = watch(result.memory, withEta(13, T0 + 27 * MIN), T0 + 27 * MIN);
    expect(result.fire).toEqual([]); // already announced
    expect(result.active).toBe("arriving_soon"); // but still on screen
  });

  it("also fires from the countdown alone, without a new snapshot", () => {
    const first = watch(NO_ALERTS, withEta(16), T0);
    expect(first.fire).toEqual([]);
    const later = watch(first.memory, withEta(16), T0 + 70_000);
    expect(later.fire).toEqual(["arriving_soon"]);
  });

  it("re-arms only after the ETA climbs back well above the threshold", () => {
    let result = watch(NO_ALERTS, withEta(14), T0);
    result = watch(result.memory, withEta(17, T0 + MIN), T0 + MIN); // small wobble
    result = watch(result.memory, withEta(14, T0 + 2 * MIN), T0 + 2 * MIN);
    expect(result.fire).toEqual([]);

    result = watch(result.memory, withEta(25, T0 + 3 * MIN), T0 + 3 * MIN); // wrong turn
    result = watch(result.memory, withEta(14, T0 + 4 * MIN), T0 + 4 * MIN);
    expect(result.fire).toEqual(["arriving_soon"]);
  });

  it("fires on first sight if the runner is already close", () => {
    expect(watch(NO_ALERTS, withEta(5), T0).fire).toEqual(["arriving_soon"]);
  });
});

describe("arrived", () => {
  const finished = snapshot({ state: "finished", arrived_at: iso(T0 + 5 * MIN) });

  it("fires when the runner arrives while we watch", () => {
    const watching = watch(NO_ALERTS, withEta(5), T0);
    const result = watch(watching.memory, finished, T0 + 5 * MIN);
    expect(result.fire).toEqual(["arrived"]);
    expect(result.active).toBe("arrived");
    expect(watch(result.memory, finished, T0 + 6 * MIN).fire).toEqual([]);
  });

  it("stays quiet when opening a link of someone who already arrived", () => {
    const result = watch(NO_ALERTS, finished, T0 + 30 * MIN);
    expect(result.fire).toEqual([]);
    expect(result.active).toBe("arrived");
  });
});

describe("safety alert", () => {
  it("fires after the configured minutes without movement", () => {
    const snap = withEta(40); // stall_alert_minutes: 10
    let result = watch(NO_ALERTS, snap, T0 + 9 * MIN);
    expect(result.fire).toEqual([]);
    result = watch(result.memory, snap, T0 + 10 * MIN);
    expect(result.fire).toEqual(["stalled"]);
    expect(result.active).toBe("stalled");
    expect(watch(result.memory, snap, T0 + 11 * MIN).fire).toEqual([]);
  });

  it("respects the runner's own threshold", () => {
    const patient = { ...withEta(40), stall_alert_minutes: 30 };
    expect(watch(NO_ALERTS, patient, T0 + 20 * MIN).active).toBeNull();
    expect(watch(NO_ALERTS, patient, T0 + 31 * MIN).active).toBe("stalled");
  });

  it("covers both a stopped runner and a silent phone", () => {
    const now = T0 + 12 * MIN;
    const stoppedButReporting = snapshot({
      position: { ...snapshot().position!, ts: iso(now - 5000) },
      last_moved_at: iso(T0),
    });
    expect(deriveStatus(stoppedButReporting, now)).toBe("stopped");
    expect(watch(NO_ALERTS, stoppedButReporting, now).fire).toEqual(["stalled"]);

    const silent = withEta(40);
    expect(deriveStatus(silent, now)).toBe("no_signal");
    expect(watch(NO_ALERTS, silent, now).fire).toEqual(["stalled"]);
  });

  it("clears when the runner moves and can fire again later", () => {
    let result = watch(NO_ALERTS, withEta(40), T0 + 10 * MIN);
    expect(result.active).toBe("stalled");
    const moved = withEta(38, T0 + 11 * MIN);
    result = watch(result.memory, moved, T0 + 11 * MIN);
    expect(result.active).toBeNull();
    result = watch(result.memory, moved, T0 + 22 * MIN);
    expect(result.fire).toEqual(["stalled"]);
  });

  it("takes priority over 'arriving soon' and suppresses it", () => {
    const result = watch(NO_ALERTS, withEta(5), T0 + 10 * MIN);
    expect(result.active).toBe("stalled");
    expect(result.fire).toEqual(["stalled"]);
  });

  it("never fires before the runner has started or after sharing ended", () => {
    const notStarted = snapshot({ position: null, last_moved_at: null, eta: null });
    expect(watch(NO_ALERTS, notStarted, T0 + 60 * MIN).active).toBeNull();
    expect(watch(NO_ALERTS, snapshot({ state: "ended" }), T0 + 60 * MIN).active).toBeNull();
  });
});
