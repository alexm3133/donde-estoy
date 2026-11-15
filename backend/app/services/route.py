"""Route geometry: a cleaned-up polyline with an elevation profile.

A raw GPX track is noisy and irregular (points every 1 m or every 500 m,
jittery elevations). :func:`build_route` turns it into a :class:`Route`:

* resampled to evenly spaced vertices (~25 m),
* with a lightly smoothed elevation profile (so noise does not turn into
  hundreds of metres of phantom ascent),
* carrying cumulative distances so we can answer "how far along is the
  runner?" and "what is left?" quickly.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.eta import Leg
from app.geo import haversine_m, to_local_xy

#: Target spacing between route vertices after resampling.
RESAMPLE_STEP_M = 25.0
#: Hard cap on vertices; very long routes get a proportionally larger step.
MAX_VERTICES = 8000
#: Elevation smoothing window: this many vertices on each side (~±50 m).
SMOOTHING_HALF_WINDOW = 2

#: When snapping a fix to the route we first look near the last known progress.
SEARCH_BEHIND_M = 200.0
SEARCH_AHEAD_M = 3000.0
#: If the best match in that window is further than this, search everywhere.
WINDOW_MAX_OFFSET_M = 60.0
#: Passes of the route within this many metres of the closest one are
#: considered ties (GPS noise) and resolved in favour of continuity with the
#: last progress. This is what keeps out-and-back and loop routes from
#: jumping to the overlapping return leg.
TIE_TOLERANCE_M = 15.0
#: When choosing between such passes, a metre backwards "costs" this many
#: metres forwards.
BACKWARD_COST = 3.0

RawPoint = tuple[float, float, float | None]


class RouteError(ValueError):
    """The supplied points cannot form a usable route."""


@dataclass(frozen=True, slots=True)
class Projection:
    """A GPS fix snapped onto the route."""

    distance_m: float  # distance along the route from its start
    offset_m: float  # how far the fix is from the route


@dataclass(frozen=True, slots=True)
class Route:
    lats: tuple[float, ...]
    lons: tuple[float, ...]
    eles: tuple[float, ...]  # all zeros when has_elevation is False
    dists: tuple[float, ...]  # cumulative distance of each vertex
    has_elevation: bool

    # -- basic facts ------------------------------------------------------

    @property
    def total_m(self) -> float:
        return self.dists[-1]

    @property
    def end(self) -> tuple[float, float]:
        return self.lats[-1], self.lons[-1]

    def climb_totals(self) -> tuple[float, float]:
        """Total (ascent, descent) in metres over the whole route."""
        ascent = descent = 0.0
        for previous, current in zip(self.eles, self.eles[1:], strict=False):
            delta = current - previous
            if delta > 0:
                ascent += delta
            else:
                descent -= delta
        return ascent, descent

    def elevation_at(self, distance_m: float) -> float:
        """Interpolated elevation at a distance along the route."""
        d = min(max(distance_m, 0.0), self.total_m)
        i = min(bisect_right(self.dists, d), len(self.dists) - 1)
        d0, d1 = self.dists[i - 1], self.dists[i]
        if d1 <= d0:
            return self.eles[i]
        t = (d - d0) / (d1 - d0)
        return self.eles[i - 1] + t * (self.eles[i] - self.eles[i - 1])

    def legs_between(self, start_m: float, end_m: float) -> list[Leg]:
        """Legs covering the route from ``start_m`` to ``end_m`` (forward)."""
        start = min(max(start_m, 0.0), self.total_m)
        end = min(max(end_m, 0.0), self.total_m)
        if end <= start:
            return []
        # Vertices strictly inside (start, end), plus the two interpolated ends.
        first = bisect_right(self.dists, start)
        last = bisect_left(self.dists, end)
        knots = [(start, self.elevation_at(start))]
        knots.extend((self.dists[i], self.eles[i]) for i in range(first, last))
        knots.append((end, self.elevation_at(end)))
        return [
            Leg(distance_m=d1 - d0, elevation_delta_m=e1 - e0)
            for (d0, e0), (d1, e1) in zip(knots, knots[1:], strict=False)
            if d1 > d0
        ]

    # -- snapping ---------------------------------------------------------

    def project(self, lat: float, lon: float, hint_m: float | None = None) -> Projection:
        """Snap a fix to the route.

        ``hint_m`` is the runner's last known progress. We search a window
        around it first and prefer matches close to it, so that routes that
        overlap themselves (loops, out-and-back) are followed in order.
        Without a hint the whole route is searched.
        """
        if hint_m is None:
            return self._best_match(lat, lon, 0, len(self.dists) - 1, None)

        lo = max(0, bisect_left(self.dists, hint_m - SEARCH_BEHIND_M) - 1)
        hi = min(len(self.dists) - 1, bisect_right(self.dists, hint_m + SEARCH_AHEAD_M))
        local = self._best_match(lat, lon, lo, hi, hint_m)
        if local.offset_m <= WINDOW_MAX_OFFSET_M:
            return local
        # Runner seems to be off the expected stretch: maybe a shortcut or a
        # GPS gap. Accept a far-away match only if it is clearly better.
        anywhere = self._best_match(lat, lon, 0, len(self.dists) - 1, hint_m)
        if anywhere.offset_m < local.offset_m - 2 * TIE_TOLERANCE_M:
            return anywhere
        return local

    def _best_match(
        self, lat: float, lon: float, lo: int, hi: int, hint_m: float | None
    ) -> Projection:
        candidates: list[tuple[float, float]] = []  # (offset, distance along)
        for i in range(lo, hi):
            ax, ay = to_local_xy(self.lats[i], self.lons[i], lat, lon)
            bx, by = to_local_xy(self.lats[i + 1], self.lons[i + 1], lat, lon)
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            # Parameter of the closest point on segment A-B to the origin (the fix).
            t = 0.0 if length_sq == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
            px, py = ax + t * dx, ay + t * dy
            offset = (px * px + py * py) ** 0.5
            along = self.dists[i] + t * (self.dists[i + 1] - self.dists[i])
            candidates.append((offset, along))

        if hint_m is None:
            offset, along = min(candidates)
        else:
            # Where the route passes near the fix more than once (out-and-back,
            # loops) each pass shows up as a separate local minimum of the
            # offset. Among the passes that are about as close as the best
            # one, follow the one nearest to where the runner already was —
            # counting steps backwards as costlier, since runners mostly move
            # forward (this resolves the turnaround of an out-and-back).
            infinity = float("inf")
            passes = [
                candidate
                for k, candidate in enumerate(candidates)
                if candidate[0] <= (candidates[k - 1][0] if k > 0 else infinity)
                and candidate[0] < (candidates[k + 1][0] if k + 1 < len(candidates) else infinity)
            ]
            best_offset = min(offset for offset, _ in passes)
            close_enough = [c for c in passes if c[0] <= best_offset + TIE_TOLERANCE_M]
            offset, along = min(
                close_enough,
                key=lambda c: c[1] - hint_m if c[1] >= hint_m else BACKWARD_COST * (hint_m - c[1]),
            )
        return Projection(distance_m=along, offset_m=offset)

    # -- persistence ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "lat": [round(v, 6) for v in self.lats],
            "lon": [round(v, 6) for v in self.lons],
            "ele": [round(v, 1) for v in self.eles],
            "dist": [round(v, 1) for v in self.dists],
            "has_elevation": self.has_elevation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Route:
        return cls(
            lats=tuple(data["lat"]),
            lons=tuple(data["lon"]),
            eles=tuple(data["ele"]),
            dists=tuple(data["dist"]),
            has_elevation=bool(data["has_elevation"]),
        )


def build_route(points: Sequence[RawPoint]) -> Route:
    """Clean raw ``(lat, lon, elevation | None)`` points into a :class:`Route`."""
    if len(points) < 2:
        raise RouteError("a route needs at least two points")

    elevations, has_elevation = _fill_elevations([p[2] for p in points])

    # Cumulative distance along the raw polyline, dropping duplicate points.
    lats, lons, eles, dists = [points[0][0]], [points[0][1]], [elevations[0]], [0.0]
    for (lat, lon, _), ele in zip(points[1:], elevations[1:], strict=False):
        step = haversine_m(lats[-1], lons[-1], lat, lon)
        if step < 0.5:
            continue
        lats.append(lat)
        lons.append(lon)
        eles.append(ele)
        dists.append(dists[-1] + step)
    total = dists[-1]
    if total < 10.0:
        raise RouteError("the route is too short")

    # Resample at a constant step by linear interpolation along the polyline.
    step = max(RESAMPLE_STEP_M, total / MAX_VERTICES)
    count = max(1, round(total / step))
    out_lat, out_lon, out_ele, out_dist = [], [], [], []
    j = 0
    for k in range(count + 1):
        d = total * k / count
        while j < len(dists) - 2 and dists[j + 1] < d:
            j += 1
        span = dists[j + 1] - dists[j]
        t = 0.0 if span <= 0 else min(1.0, max(0.0, (d - dists[j]) / span))
        out_lat.append(lats[j] + t * (lats[j + 1] - lats[j]))
        out_lon.append(lons[j] + t * (lons[j + 1] - lons[j]))
        out_ele.append(eles[j] + t * (eles[j + 1] - eles[j]))
        out_dist.append(d)

    return Route(
        lats=tuple(out_lat),
        lons=tuple(out_lon),
        eles=tuple(_smooth(out_ele)),
        dists=tuple(out_dist),
        has_elevation=has_elevation,
    )


def _fill_elevations(values: Sequence[float | None]) -> tuple[list[float], bool]:
    """Fill gaps with the nearest known elevation; all zeros if none known."""
    if all(v is None for v in values):
        return [0.0] * len(values), False
    filled: list[float] = []
    first_known = next(v for v in values if v is not None)
    last = first_known
    for value in values:
        if value is not None:
            last = value
        filled.append(last)
    return filled, True


def _smooth(values: Sequence[float]) -> list[float]:
    """Centred moving average.

    The window stays symmetric and shrinks towards the ends, so the first and
    last elevations (and therefore the route's net climb) are preserved.
    """
    n = len(values)
    smoothed = []
    for i in range(n):
        half = min(SMOOTHING_HALF_WINDOW, i, n - 1 - i)
        smoothed.append(sum(values[i - half : i + half + 1]) / (2 * half + 1))
    return smoothed
