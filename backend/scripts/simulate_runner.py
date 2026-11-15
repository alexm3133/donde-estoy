"""Simulate a runner against a running API — handy for working on the viewer UI.

Creates a session on a synthetic mountain route (or your own GPX), back-fills
part of the outing, prints the viewer link, then keeps "running" in real time.

    python scripts/simulate_runner.py                       # 40 % done, then live
    python scripts/simulate_runner.py --gpx my.gpx --speed 4
    python scripts/simulate_runner.py --progress 0.9 --no-live

Requires the dev dependencies (httpx).
"""

from __future__ import annotations

import argparse
import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.eta import Leg, tobler_speed_ms
from app.services.gpx import parse_gpx
from app.services.route import Route, build_route

FIX_INTERVAL_S = 5.0


def synthetic_route() -> list[tuple[float, float, float]]:
    """A winding 6 km trail: gentle start, a 400 m climb, a long descent."""
    points = []
    for i in range(301):
        t = i / 300
        lat = 42.30 + 0.035 * t + 0.004 * math.sin(t * 9)
        lon = 1.95 + 0.03 * t + 0.006 * math.sin(t * 5 + 1)
        elevation = (
            1200 + 400 * math.sin(min(t, 0.55) / 0.55 * math.pi / 2) - 520 * max(0, t - 0.55) / 0.45
        )
        points.append((lat, lon, elevation))
    return points


def fixes_along(route: Route, pace_factor: float):
    """Yield ``(seconds_from_start, lat, lon, ele, distance)`` every few seconds."""
    distance, elapsed = 0.0, 0.0
    while True:
        i = min(
            max(1, next((k for k, d in enumerate(route.dists) if d >= distance), 1)),
            len(route.dists) - 1,
        )
        span = route.dists[i] - route.dists[i - 1] or 1.0
        f = (distance - route.dists[i - 1]) / span
        lat = route.lats[i - 1] + f * (route.lats[i] - route.lats[i - 1])
        lon = route.lons[i - 1] + f * (route.lons[i] - route.lons[i - 1])
        yield elapsed, lat, lon, route.elevation_at(distance), distance
        if distance >= route.total_m:
            return
        grade = Leg(span, route.eles[i] - route.eles[i - 1]).grade
        distance = min(
            route.total_m, distance + pace_factor * tobler_speed_ms(grade) * FIX_INTERVAL_S
        )
        elapsed += FIX_INTERVAL_S


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--web", default="http://localhost:5173", help="frontend base URL (for the link)"
    )
    parser.add_argument(
        "--gpx", type=Path, help="GPX file to follow instead of the synthetic route"
    )
    parser.add_argument("--name", default="Alex")
    parser.add_argument("--pace", type=float, default=1.6, help="pace factor vs Tobler's walker")
    parser.add_argument(
        "--progress", type=float, default=0.4, help="fraction already covered at start"
    )
    parser.add_argument(
        "--speed", type=float, default=1.0, help="time acceleration of the live part"
    )
    parser.add_argument("--stall-minutes", type=int, default=10)
    parser.add_argument("--no-live", action="store_true", help="stop after the back-fill")
    args = parser.parse_args()

    raw = parse_gpx(args.gpx.read_bytes())[1] if args.gpx else synthetic_route()
    route = build_route(raw)
    fixes = list(fixes_along(route, args.pace))
    split = next(
        (k for k, fix in enumerate(fixes) if fix[4] >= args.progress * route.total_m), len(fixes)
    )

    with httpx.Client(base_url=args.api, timeout=30) as client:
        created = (
            client.post(
                "/api/sessions",
                json={
                    "runner_name": args.name,
                    "stall_alert_minutes": args.stall_minutes,
                    "route_points": [list(p) for p in raw],
                },
            )
            .raise_for_status()
            .json()
        )
        headers = {"Authorization": f"Bearer {created['runner_token']}"}
        url = f"/api/sessions/{created['id']}/positions"
        print(f"viewer link: {args.web}/s/{created['view_token']}")

        def send(batch, start: datetime) -> dict:
            body = [
                {
                    "lat": lat,
                    "lon": lon,
                    "ele": ele,
                    "accuracy": 6,
                    "ts": (start + timedelta(seconds=s)).isoformat(),
                }
                for s, lat, lon, ele, _ in batch
            ]
            return (
                client.post(url, json={"positions": body}, headers=headers)
                .raise_for_status()
                .json()
            )

        # Back-fill: pretend the outing started long enough ago to be here now.
        done = fixes[:split]
        start = datetime.now(UTC) - timedelta(seconds=done[-1][0] if done else 0)
        for k in range(0, len(done), 400):
            send(done[k : k + 400], start)
        print(
            f"back-filled {len(done)} fixes ({args.progress:.0%} of {route.total_m / 1000:.1f} km)"
        )
        if args.no_live:
            return

        for fix in fixes[split:]:
            time.sleep(FIX_INTERVAL_S / args.speed)
            # Shift the timeline so each fix is stamped "now" despite the speed-up.
            snapshot = send([fix], datetime.now(UTC) - timedelta(seconds=fix[0]))["snapshot"]
            eta = snapshot["eta"]["seconds"] / 60 if snapshot["eta"] else float("nan")
            print(f"  {fix[4] / 1000:5.2f} km  eta {eta:5.1f} min  state={snapshot['state']}")
            if snapshot["state"] != "active":
                break


if __name__ == "__main__":
    main()
