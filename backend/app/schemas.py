"""Request / response shapes of the HTTP API (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
#: ``[lat, lon, elevation | null]``
RoutePoint = tuple[Latitude, Longitude, float | None]

MAX_ROUTE_POINTS = 20_000
MAX_POSITIONS_PER_BATCH = 500


class LatLon(BaseModel):
    lat: Latitude
    lon: Longitude


# -- routes -------------------------------------------------------------------


class RouteOut(BaseModel):
    """A processed route, ready to draw: map line + elevation profile."""

    #: ``[lat, lon, elevation_m, distance_from_start_m]`` per vertex.
    points: list[tuple[float, float, float, float]]
    distance_m: float
    ascent_m: float
    descent_m: float
    has_elevation: bool


class ParsedRoute(RouteOut):
    name: str | None = None
    #: Raw points to send back in ``SessionCreate.route_points``.
    raw_points: list[RoutePoint]


# -- live snapshot (what viewers see) ------------------------------------------


class PositionOut(BaseModel):
    lat: float
    lon: float
    ele: float | None = None
    accuracy: float | None = None
    ts: datetime


class ProgressOut(BaseModel):
    #: Along-route figures are null for tap-on-map sessions.
    done_m: float | None = None
    total_m: float | None = None
    remaining_m: float
    remaining_ascent_m: float
    remaining_descent_m: float
    off_route: bool = False


class EtaOut(BaseModel):
    """Moving time left, as of ``computed_at``.

    Clients show ``computed_at + seconds`` while the runner moves, and
    ``now + seconds`` while they are stopped (the arrival time slides).
    """

    seconds: float
    low_seconds: float
    high_seconds: float
    confidence: Literal["low", "medium", "high"]
    computed_at: datetime


class StatsOut(BaseModel):
    moving_time_s: float
    distance_m: float


class Snapshot(BaseModel):
    """Current state of a session. Pushed over the WebSocket on every change."""

    runner_name: str
    activity: Literal["run", "hike"]
    state: Literal["active", "finished", "ended"]
    #: Server clock, so clients can correct their own when computing ages.
    server_time: datetime
    created_at: datetime
    expires_at: datetime
    stall_alert_minutes: int
    destination: LatLon | None = None
    has_route: bool
    position: PositionOut | None = None
    started_at: datetime | None = None
    #: Last time the runner was seen moving; drives "stopped" and the safety alert.
    last_moved_at: datetime | None = None
    arrived_at: datetime | None = None
    progress: ProgressOut | None = None
    eta: EtaOut | None = None
    stats: StatsOut


class SessionView(Snapshot):
    """Snapshot plus the heavy, rarely-changing parts (initial page load)."""

    route: RouteOut | None = None
    #: Where the runner has been: ``[lat, lon]`` pairs, oldest first.
    track: list[tuple[float, float]] = []


# -- sessions (runner side) ---------------------------------------------------


class SessionCreate(BaseModel):
    runner_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
    ]
    activity: Literal["run", "hike"] = "run"
    stall_alert_minutes: int = Field(default=10, ge=2, le=120)
    duration_hours: float | None = Field(default=None, ge=0.5)
    #: Either a destination point...
    destination: LatLon | None = None
    #: ...or a route to follow (its last point is the destination).
    route_points: list[RoutePoint] | None = Field(default=None, max_length=MAX_ROUTE_POINTS)

    @model_validator(mode="after")
    def _needs_a_destination(self) -> SessionCreate:
        if self.destination is None and not self.route_points:
            raise ValueError("either destination or route_points is required")
        return self


class SessionCreated(BaseModel):
    id: str
    #: Secret for the runner's device. Shown once; only its hash is stored.
    runner_token: str
    view_token: str
    share_url: str
    expires_at: datetime
    snapshot: Snapshot


class PositionIn(BaseModel):
    lat: Latitude
    lon: Longitude
    ele: float | None = None
    accuracy: float | None = Field(default=None, ge=0)
    #: When the fix was taken, by the device clock.
    ts: datetime


class PositionBatch(BaseModel):
    positions: list[PositionIn] = Field(min_length=1, max_length=MAX_POSITIONS_PER_BATCH)
    #: Device clock at send time; lets the server cancel out clock skew.
    sent_at: datetime | None = None


class PositionsAccepted(BaseModel):
    accepted: int
    snapshot: Snapshot
