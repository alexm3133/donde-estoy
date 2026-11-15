/**
 * Runner-side engine: GPS -> buffer -> server, plus the screen wake lock.
 */
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { RouteVertex, Snapshot } from "../api/types";
import { haversineM } from "../domain/geo";
import { createLocationProvider, type LocationErrorCode, type LocationFix } from "../location";
import { bufferKey, type StoredSession } from "./sessionStore";
import { PositionUploader } from "./uploader";
import { keepScreenOn, type WakeLockState } from "./wakeLock";

/** A fix is kept if it is this much later, or this much further, than the last one. */
const MIN_INTERVAL_MS = 3000;
const MIN_DISTANCE_M = 10;
/** How often buffered fixes are sent. */
const FLUSH_INTERVAL_MS = 5000;

export type GpsState = "starting" | "ok" | LocationErrorCode;

export interface RunnerTracking {
  gps: GpsState;
  lastFix: LocationFix | null;
  /** Fixes waiting to be uploaded (grows while there is no coverage). */
  pending: number;
  /** False while uploads are failing. */
  online: boolean;
  wakeLock: WakeLockState;
  /** Latest state acknowledged by the server. */
  snapshot: Snapshot | null;
  /** The server no longer knows the session (expired / stopped). */
  gone: boolean;
}

export function useRunnerTracking(
  session: StoredSession,
  /** While false nothing is tracked (session finished, or still loading). */
  enabled: boolean,
  /** Route for the simulator when `session.demo` is set. */
  demoRoute: RouteVertex[] | null,
): RunnerTracking {
  const [state, setState] = useState<RunnerTracking>({
    gps: "starting",
    lastFix: null,
    pending: 0,
    online: true,
    wakeLock: "inactive",
    snapshot: null,
    gone: false,
  });
  const lastKept = useRef<LocationFix | null>(null);

  useEffect(() => {
    if (!enabled) return;
    if (session.demo && !demoRoute) return; // wait for the route to simulate on
    const patch = (changes: Partial<RunnerTracking>) =>
      setState((current) => ({ ...current, ...changes }));

    const uploader = new PositionUploader({
      send: (batch) => api.postPositions(session.id, session.runnerToken, batch),
      storage: localStorage,
      storageKey: bufferKey(),
      onSnapshot: (snapshot) => patch({ snapshot }),
      onGone: () => patch({ gone: true }),
      onPendingChange: (pending) => patch({ pending }),
    });
    patch({ pending: uploader.pending });

    const flush = async () => {
      const result = await uploader.flush();
      if (result === "sent") patch({ online: true });
      if (result === "offline") patch({ online: false });
    };

    const provider = createLocationProvider(session.demo ? demoRoute : null);
    provider.start({
      onFix(fix) {
        patch({ gps: "ok", lastFix: fix });
        const last = lastKept.current;
        const keep =
          !last ||
          fix.ts - last.ts >= MIN_INTERVAL_MS ||
          haversineM(last.lat, last.lon, fix.lat, fix.lon) >= MIN_DISTANCE_M;
        if (!keep) return;
        lastKept.current = fix;
        uploader.enqueue({
          lat: fix.lat,
          lon: fix.lon,
          ele: fix.ele,
          accuracy: fix.accuracy,
          ts: new Date(fix.ts).toISOString(),
        });
      },
      onError: (code) => patch({ gps: code }),
    });

    const timer = window.setInterval(flush, FLUSH_INTERVAL_MS);
    // Coverage is back: do not wait for the next tick.
    window.addEventListener("online", flush);
    void flush();
    const releaseWakeLock = keepScreenOn((wakeLock) => patch({ wakeLock }));

    return () => {
      provider.stop();
      window.clearInterval(timer);
      window.removeEventListener("online", flush);
      releaseWakeLock();
      void uploader.flush(); // best effort: hand over what is left
    };
  }, [session, enabled, demoRoute]);

  return state;
}
