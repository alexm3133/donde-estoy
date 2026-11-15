import { describe, expect, it } from "vitest";
import { arrivalTimeMs, deriveStatus, NO_SIGNAL_AFTER_S, STOPPED_AFTER_S } from "./status";
import { iso, snapshot, T0 } from "./testing";

const MIN = 60_000;

describe("deriveStatus", () => {
  it("follows the session state when it is over", () => {
    expect(deriveStatus(snapshot({ state: "ended" }), T0)).toBe("ended");
    expect(deriveStatus(snapshot({ state: "finished" }), T0)).toBe("finished");
  });

  it("is waiting until the first position arrives", () => {
    expect(deriveStatus(snapshot({ position: null, last_moved_at: null }), T0)).toBe("waiting");
  });

  it("is moving right after a fix with movement", () => {
    expect(deriveStatus(snapshot(), T0 + 10_000)).toBe("moving");
  });

  it("is stopped when fixes keep coming without movement", () => {
    const now = T0 + (STOPPED_AFTER_S + 5) * 1000;
    const stillReporting = snapshot({ position: { ...snapshot().position!, ts: iso(now - 4000) } });
    expect(deriveStatus(stillReporting, now)).toBe("stopped");
  });

  it("is no_signal when fixes stop arriving, whatever the last movement", () => {
    expect(deriveStatus(snapshot(), T0 + (NO_SIGNAL_AFTER_S + 1) * 1000)).toBe("no_signal");
  });
});

describe("arrivalTimeMs", () => {
  it("has no estimate before the first fix or after sharing ended", () => {
    expect(arrivalTimeMs(snapshot({ eta: null }), "moving", T0)).toBeNull();
    expect(arrivalTimeMs(snapshot(), "waiting", T0)).toBeNull();
    expect(arrivalTimeMs(snapshot(), "ended", T0)).toBeNull();
  });

  it("stays fixed while moving, so the countdown runs", () => {
    const fixed = T0 + 40 * MIN;
    expect(arrivalTimeMs(snapshot(), "moving", T0)).toBe(fixed);
    expect(arrivalTimeMs(snapshot(), "moving", T0 + 30_000)).toBe(fixed);
  });

  it("slides later while stopped: the time left does not shrink", () => {
    const later = T0 + 5 * MIN;
    expect(arrivalTimeMs(snapshot(), "stopped", later)).toBe(later + 40 * MIN);
  });

  it("assumes the runner keeps going during a signal gap, but never in the past", () => {
    expect(arrivalTimeMs(snapshot(), "no_signal", T0 + 10 * MIN)).toBe(T0 + 40 * MIN);
    expect(arrivalTimeMs(snapshot(), "no_signal", T0 + 50 * MIN)).toBe(T0 + 50 * MIN);
  });

  it("reports the actual arrival once finished", () => {
    const arrived = snapshot({ state: "finished", arrived_at: iso(T0 + 7 * MIN) });
    expect(arrivalTimeMs(arrived, "finished", T0 + 20 * MIN)).toBe(T0 + 7 * MIN);
  });
});
