/**
 * The location layer.
 *
 * Everything that needs the runner's position talks to this interface, never
 * to `navigator.geolocation` directly. Today there are two implementations:
 *
 *  - {@link BrowserLocationProvider}: the Web Geolocation API. Works only
 *    while the page is visible and the screen is on.
 *  - {@link SimulatedLocationProvider}: follows a route; used by the demo.
 *
 * A native build can add a third one backed by a Capacitor
 * background-geolocation plugin (keeps tracking with the screen off) and
 * select it in `createLocationProvider()` — nothing else has to change.
 */

export interface LocationFix {
  lat: number;
  lon: number;
  /** Metres above sea level, when the device knows it. */
  ele: number | null;
  /** Horizontal accuracy radius in metres. */
  accuracy: number | null;
  /** When the fix was taken (epoch milliseconds, device clock). */
  ts: number;
}

export type LocationErrorCode = "denied" | "unavailable" | "unsupported";

export interface LocationListener {
  onFix(fix: LocationFix): void;
  onError(code: LocationErrorCode): void;
}

export interface LocationProvider {
  /** Start delivering fixes. Safe to call again after `stop()`. */
  start(listener: LocationListener): void;
  stop(): void;
  /** True if this provider keeps working with the screen off. */
  readonly worksInBackground: boolean;
}
