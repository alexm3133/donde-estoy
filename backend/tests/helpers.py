"""Shared test utilities: synthetic routes and a simulated runner."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator

from app.eta import Leg, Terrain, classify, tobler_speed_ms
from app.geo import METERS_PER_DEGREE
from app.services.route import RawPoint, Route
from app.services.tracker import Fix

START_LAT, START_LON = 42.0, 1.5  # somewhere in the Pyrenees


def north_of_start(meters: float, east_m: float = 0.0) -> tuple[float, float]:
    """Point ``meters`` north (and optionally east) of the test origin."""
    lat = START_LAT + meters / METERS_PER_DEGREE
    lon = START_LON + east_m / (METERS_PER_DEGREE * math.cos(math.radians(START_LAT)))
    return lat, lon


def straight_route(profile: list[tuple[float, float]], step_m: float = 20.0) -> list[RawPoint]:
    """Raw points heading due north following ``[(distance_m, elevation_m), ...]``."""
    points: list[RawPoint] = []
    for (d0, e0), (d1, e1) in zip(profile, profile[1:], strict=False):
        steps = max(1, round((d1 - d0) / step_m))
        for k in range(steps):
            d = d0 + (d1 - d0) * k / steps
            lat, lon = north_of_start(d)
            points.append((lat, lon, e0 + (e1 - e0) * k / steps))
    lat, lon = north_of_start(profile[-1][0])
    points.append((lat, lon, profile[-1][1]))
    return points


#: 2 km flat, 3 km climbing 450 m (15 %), 3 km descending 450 m, 2 km flat.
MOUNTAIN_PROFILE = [(0, 1000), (2000, 1000), (5000, 1450), (8000, 1000), (10000, 1000)]


def simulate_run(
    route: Route,
    factors: dict[Terrain, float],
    *,
    interval_s: float = 5.0,
    noise_m: float = 0.0,
    start_ts: float = 1_700_000_000.0,
    pause: Callable[[float], float] | None = None,
    seed: int = 7,
) -> Iterator[tuple[Fix, float]]:
    """Yield ``(fix, true_distance_along_route)`` for a runner following ``route``.

    The runner moves at ``factor[terrain] * tobler(grade)`` — i.e. exactly the
    family of behaviours the ETA model assumes, with per-terrain factors the
    engine has to discover. ``pause(distance)`` may return seconds to stand
    still when reaching that distance (called once per tick).
    """
    rng = random.Random(seed)
    distance, ts = 0.0, start_ts
    while True:
        lat = _interp(route.dists, route.lats, distance)
        lon = _interp(route.dists, route.lons, distance)
        if noise_m:
            lat += rng.gauss(0, noise_m) / METERS_PER_DEGREE
            lon += rng.gauss(0, noise_m) / METERS_PER_DEGREE
        yield Fix(lat=lat, lon=lon, ts=ts, ele=route.elevation_at(distance), accuracy=8.0), distance
        if distance >= route.total_m:
            return
        wait = pause(distance) if pause else 0.0
        if wait:
            ts += wait
            continue
        ahead = min(distance + 5.0, route.total_m)
        grade = Leg(
            max(ahead - distance, 0.01), route.elevation_at(ahead) - route.elevation_at(distance)
        ).grade
        speed = factors[classify(grade)] * tobler_speed_ms(grade)
        distance = min(route.total_m, distance + speed * interval_s)
        ts += interval_s


def _interp(xs, ys, x: float) -> float:
    from bisect import bisect_right

    i = min(max(bisect_right(xs, x), 1), len(xs) - 1)
    span = xs[i] - xs[i - 1]
    t = 0.0 if span <= 0 else (x - xs[i - 1]) / span
    return ys[i - 1] + t * (ys[i] - ys[i - 1])


def gpx_document(points: list[RawPoint], name: str = "Test route") -> bytes:
    body = "".join(
        f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}">'
        + (f"<ele>{ele:.1f}</ele>" if ele is not None else "")
        + "</trkpt>"
        for lat, lon, ele in points
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="tests" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><name>{name}</name><trkseg>{body}</trkseg></trk></gpx>"
    ).encode()
