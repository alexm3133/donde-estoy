"""Turns a stream of GPS fixes into progress, status and an ETA.

This is the session's state machine. It is deliberately free of I/O: it takes
the previous :class:`TrackerState` plus a new :class:`Fix` and updates the
state. The API layer loads/saves that state as JSON on the session row.

Responsibilities
----------------
* reject bad fixes (poor accuracy, out of order, impossible jumps),
* detect movement vs. standing still (``last_moved_at``),
* snap the runner to the route and measure progress,
* feed clean "moved X in T seconds" observations to the pace calibration,
* detect arrival,
* ask the ETA engine for the time left.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from app.eta import Leg, PaceCalibration, estimate, new_calibration
from app.geo import haversine_m

from .route import Route

# -- fix filtering -----------------------------------------------------------
#: Fixes with a worse reported accuracy than this are ignored.
MAX_ACCURACY_M = 100.0
#: Faster than this between two fixes means a GPS glitch (≈ 43 km/h).
MAX_SPEED_MS = 12.0
#: ...unless it keeps happening, in which case the *previous* fix was the bad one.
MAX_REJECTED_STREAK = 3

# -- movement ----------------------------------------------------------------
#: Leaving a circle of this radius counts as "has moved".
STILL_RADIUS_M = 15.0

# -- calibration segments ----------------------------------------------------
#: An observation needs at least this much forward progress and time...
MIN_ADVANCE_M = 30.0
MIN_SEGMENT_S = 10.0
#: ...and without that much progress after this long, the runner is pausing:
#: we drop the segment so that breaks do not count as slow pace.
PAUSE_RESET_S = 90.0
#: Gaps longer than this (lost GPS) are not trusted for calibration.
MAX_SEGMENT_S = 180.0
#: Further than this from the route, progress along it means little.
OFF_ROUTE_M = 100.0

# -- arrival / free navigation ----------------------------------------------
ARRIVAL_RADIUS_M = 30.0
#: With no route we only know the straight line; trails are longer than that.
DETOUR_FACTOR = 1.3


@dataclass(slots=True)
class Fix:
    """One GPS reading. ``ts`` is a UNIX timestamp in seconds."""

    lat: float
    lon: float
    ts: float
    ele: float | None = None
    accuracy: float | None = None


@dataclass(slots=True)
class TrackerState:
    """Everything we remember between fixes. JSON-serialisable."""

    calibration: dict[str, Any] | None = None
    last_fix: dict[str, Any] | None = None
    started_at: float | None = None
    last_moved_at: float | None = None
    still_lat: float | None = None
    still_lon: float | None = None
    #: Distance along the route (route sessions only).
    progress_m: float | None = None
    #: Distance between the runner and the route.
    offset_m: float = 0.0
    #: Start of the calibration segment currently being measured.
    anchor: dict[str, float] | None = None
    moving_time_s: float = 0.0
    distance_m: float = 0.0
    rejected_streak: int = 0
    arrived_at: float | None = None
    #: Latest ETA: seconds / low / high / confidence / computed_at.
    eta: dict[str, Any] | None = None
    #: What is left: distance_m / ascent_m / descent_m.
    remaining: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TrackerState:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


class Tracker:
    """Applies fixes to a :class:`TrackerState`."""

    def __init__(
        self,
        state: TrackerState,
        *,
        route: Route | None,
        destination: tuple[float, float],
        activity: str,
    ) -> None:
        self.state = state
        self.route = route
        self.destination = destination
        self.calibration = (
            PaceCalibration.from_dict(state.calibration)
            if state.calibration
            else new_calibration(activity)
        )

    def process(self, fix: Fix) -> bool:
        """Apply one fix. Returns ``False`` if it was rejected as unusable."""
        s = self.state
        if s.arrived_at is not None:
            return False
        if fix.accuracy is not None and fix.accuracy > MAX_ACCURACY_M:
            return False

        teleported = False
        if s.last_fix is not None:
            elapsed = fix.ts - s.last_fix["ts"]
            if elapsed <= 0:
                return False  # duplicate or out of order
            jump = haversine_m(s.last_fix["lat"], s.last_fix["lon"], fix.lat, fix.lon)
            if jump > 50.0 and jump / elapsed > MAX_SPEED_MS:
                if s.rejected_streak < MAX_REJECTED_STREAK:
                    s.rejected_streak += 1
                    return False
                teleported = True  # consistent new location: believe it
        s.rejected_streak = 0

        if teleported or s.started_at is None:
            s.started_at = s.started_at or fix.ts
            s.last_moved_at = fix.ts
            s.still_lat, s.still_lon = fix.lat, fix.lon
            s.anchor = None
            if teleported:
                s.progress_m = None
        else:
            self._detect_movement(fix)

        if self.route is not None:
            # First fix: assume the runner is near the start (hint 0), which
            # matters for loops whose start and finish coincide.
            hint = s.progress_m if s.progress_m is not None else (None if teleported else 0.0)
            projection = self.route.project(fix.lat, fix.lon, hint)
            s.progress_m = projection.distance_m
            s.offset_m = projection.offset_m

        self._calibrate(fix)
        s.last_fix = {
            "lat": fix.lat,
            "lon": fix.lon,
            "ele": fix.ele,
            "accuracy": fix.accuracy,
            "ts": fix.ts,
        }
        self._update_eta(fix)
        s.calibration = self.calibration.to_dict()
        return True

    # -- internals --------------------------------------------------------

    def _detect_movement(self, fix: Fix) -> None:
        s = self.state
        moved = haversine_m(s.still_lat, s.still_lon, fix.lat, fix.lon)
        # A fuzzy fix must clear its own error radius to count as movement.
        threshold = max(STILL_RADIUS_M, min(fix.accuracy or 0.0, 40.0))
        if moved > threshold:
            s.distance_m += moved
            s.last_moved_at = fix.ts
            s.still_lat, s.still_lon = fix.lat, fix.lon

    def _set_anchor(self, fix: Fix) -> None:
        self.state.anchor = {
            "ts": fix.ts,
            "lat": fix.lat,
            "lon": fix.lon,
            "progress_m": self.state.progress_m or 0.0,
        }

    def _calibrate(self, fix: Fix) -> None:
        """Close a calibration segment when enough ground has been covered."""
        s = self.state
        anchor = s.anchor
        if anchor is None:
            self._set_anchor(fix)
            return

        elapsed = fix.ts - anchor["ts"]
        if self.route is not None:
            advance = (s.progress_m or 0.0) - anchor["progress_m"]
            off_route = s.offset_m > OFF_ROUTE_M
        else:
            advance = haversine_m(anchor["lat"], anchor["lon"], fix.lat, fix.lon)
            off_route = False

        if off_route or advance < -MIN_ADVANCE_M or elapsed > MAX_SEGMENT_S:
            self._set_anchor(fix)  # unusable stretch: start over from here
        elif advance >= MIN_ADVANCE_M and elapsed >= MIN_SEGMENT_S:
            if self.route is not None:
                legs = self.route.legs_between(anchor["progress_m"], s.progress_m or 0.0)
            else:
                # No profile to lean on: treat ground as flat, so the factor
                # learned is simply "average speed over this terrain".
                legs = [Leg(distance_m=advance)]
            if self.calibration.observe(legs, elapsed):
                s.moving_time_s += elapsed
            self._set_anchor(fix)
        elif elapsed > PAUSE_RESET_S:
            self._set_anchor(fix)  # barely moved for a while: a break

    def _update_eta(self, fix: Fix) -> None:
        s = self.state
        if self.route is not None:
            progress = s.progress_m or 0.0
            legs = self.route.legs_between(progress, self.route.total_m)
            if s.offset_m > ARRIVAL_RADIUS_M:
                legs.insert(0, Leg(distance_m=s.offset_m))  # get back on the route first
            arrived = (
                self.route.total_m - progress <= ARRIVAL_RADIUS_M
                and s.offset_m <= 2 * ARRIVAL_RADIUS_M
            )
        else:
            straight = haversine_m(fix.lat, fix.lon, *self.destination)
            legs = [Leg(distance_m=straight * DETOUR_FACTOR)]
            arrived = straight <= ARRIVAL_RADIUS_M

        if arrived:
            s.arrived_at = fix.ts
            s.eta = {
                "seconds": 0.0,
                "low_seconds": 0.0,
                "high_seconds": 0.0,
                "confidence": "high",
                "computed_at": fix.ts,
            }
            s.remaining = {"distance_m": 0.0, "ascent_m": 0.0, "descent_m": 0.0}
            return

        result = estimate(legs, self.calibration)
        s.eta = {
            "seconds": round(result.seconds, 1),
            "low_seconds": round(result.low_seconds, 1),
            "high_seconds": round(result.high_seconds, 1),
            "confidence": result.confidence,
            "computed_at": fix.ts,
        }
        s.remaining = {
            "distance_m": round(result.distance_m, 1),
            "ascent_m": round(result.ascent_m, 1),
            "descent_m": round(result.descent_m, 1),
        }
