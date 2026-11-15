import type { RouteVertex } from "../api/types";
import type { LocationListener, LocationProvider } from "./LocationProvider";

const TICK_MS = 1000;

/**
 * Pretends to be a runner following a route. Used by the in-app demo, so the
 * whole product can be tried from a sofa.
 *
 * Speed follows Tobler's hiking function (slower on steep ground) times
 * `paceFactor`, so the simulated runner behaves like the ETA model expects
 * a human to — just faster, to keep demos short.
 */
export class SimulatedLocationProvider implements LocationProvider {
  readonly worksInBackground = false;
  private timer: number | null = null;
  private distance = 0;

  constructor(
    private readonly route: RouteVertex[],
    private readonly paceFactor = 5,
  ) {}

  start(listener: LocationListener): void {
    this.stop();
    const total = this.route[this.route.length - 1][3];
    const tick = () => {
      const [lat, lon, ele, grade] = this.at(this.distance);
      listener.onFix({ lat, lon, ele, accuracy: 6, ts: Date.now() });
      if (this.distance >= total) return this.stop();
      const walkingKmh = 6 * Math.exp(-3.5 * Math.abs(grade + 0.05));
      this.distance = Math.min(
        total,
        this.distance + ((walkingKmh * this.paceFactor) / 3.6) * (TICK_MS / 1000),
      );
    };
    tick();
    this.timer = window.setInterval(tick, TICK_MS);
  }

  stop(): void {
    if (this.timer !== null) window.clearInterval(this.timer);
    this.timer = null;
  }

  /** Interpolated `[lat, lon, ele, grade]` at a distance along the route. */
  private at(distance: number): [number, number, number, number] {
    const points = this.route;
    let i = 1;
    while (i < points.length - 1 && points[i][3] < distance) i++;
    const [a, b] = [points[i - 1], points[i]];
    const span = b[3] - a[3] || 1;
    const t = Math.min(1, Math.max(0, (distance - a[3]) / span));
    return [
      a[0] + t * (b[0] - a[0]),
      a[1] + t * (b[1] - a[1]),
      a[2] + t * (b[2] - a[2]),
      (b[2] - a[2]) / span,
    ];
  }
}
