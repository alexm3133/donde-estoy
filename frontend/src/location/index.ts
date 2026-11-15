import type { RouteVertex } from "../api/types";
import { BrowserLocationProvider } from "./BrowserLocationProvider";
import type { LocationProvider } from "./LocationProvider";
import { SimulatedLocationProvider } from "./SimulatedLocationProvider";

export type { LocationErrorCode, LocationFix, LocationProvider } from "./LocationProvider";

/**
 * Picks the location source for a runner session.
 *
 * This is the single place to plug in a native background provider later:
 *
 *   if (Capacitor.isNativePlatform()) return new CapacitorBackgroundProvider();
 */
export function createLocationProvider(demoRoute?: RouteVertex[] | null): LocationProvider {
  if (demoRoute?.length) return new SimulatedLocationProvider(demoRoute);
  return new BrowserLocationProvider();
}
