/**
 * Screen Wake Lock: keeps the display on so the browser keeps delivering GPS
 * fixes. The lock is released by the browser whenever the page is hidden, so
 * we re-acquire it each time the page becomes visible again.
 */
export type WakeLockState = "active" | "inactive" | "unsupported";

export function keepScreenOn(onChange: (state: WakeLockState) => void): () => void {
  if (!("wakeLock" in navigator)) {
    onChange("unsupported");
    return () => {};
  }

  let sentinel: WakeLockSentinel | null = null;
  let cancelled = false;

  const acquire = async () => {
    if (cancelled || document.visibilityState !== "visible" || sentinel) return;
    try {
      const lock = await navigator.wakeLock.request("screen");
      if (cancelled) {
        void lock.release();
        return;
      }
      sentinel = lock;
      onChange("active");
      lock.addEventListener("release", () => {
        sentinel = null;
        if (!cancelled) onChange("inactive");
      });
    } catch {
      onChange("inactive"); // e.g. battery saver refuses the lock
    }
  };

  const onVisibility = () => void acquire();
  document.addEventListener("visibilitychange", onVisibility);
  void acquire();

  return () => {
    cancelled = true;
    document.removeEventListener("visibilitychange", onVisibility);
    void sentinel?.release();
  };
}
