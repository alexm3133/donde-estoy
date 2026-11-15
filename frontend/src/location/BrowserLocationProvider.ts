import type { LocationListener, LocationProvider } from "./LocationProvider";

/** Web Geolocation API (`navigator.geolocation.watchPosition`). */
export class BrowserLocationProvider implements LocationProvider {
  readonly worksInBackground = false;
  private watchId: number | null = null;

  start(listener: LocationListener): void {
    if (!("geolocation" in navigator)) {
      listener.onError("unsupported");
      return;
    }
    this.stop();
    this.watchId = navigator.geolocation.watchPosition(
      (position) =>
        listener.onFix({
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          ele: position.coords.altitude,
          accuracy: position.coords.accuracy,
          ts: position.timestamp,
        }),
      (error) =>
        listener.onError(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable"),
      // Fresh GPS fixes only; a timeout just triggers "unavailable" and the
      // watch keeps trying.
      { enableHighAccuracy: true, maximumAge: 0, timeout: 30_000 },
    );
  }

  stop(): void {
    if (this.watchId !== null) navigator.geolocation.clearWatch(this.watchId);
    this.watchId = null;
  }
}
