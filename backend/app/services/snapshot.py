"""Builds the public view of a session from the database row."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db import utcnow
from app.models import STATE_ENDED, LiveSession
from app.schemas import (
    EtaOut,
    LatLon,
    PositionOut,
    ProgressOut,
    RouteOut,
    Snapshot,
    StatsOut,
)

from .route import Route
from .tracker import OFF_ROUTE_M, TrackerState


def _dt(timestamp: float | None) -> datetime | None:
    return None if timestamp is None else datetime.fromtimestamp(timestamp, UTC)


def build_snapshot(session: LiveSession) -> Snapshot:
    state = TrackerState.from_dict(session.tracker)
    snapshot = Snapshot(
        runner_name=session.runner_name,
        activity=session.activity,
        state=session.state,
        server_time=utcnow(),
        created_at=session.created_at,
        expires_at=session.expires_at,
        stall_alert_minutes=session.stall_alert_minutes,
        has_route=session.route is not None,
        stats=StatsOut(moving_time_s=state.moving_time_s, distance_m=state.distance_m),
    )
    if session.state == STATE_ENDED:
        return snapshot  # location data is gone; say nothing more

    if session.dest_lat is not None and session.dest_lon is not None:
        snapshot.destination = LatLon(lat=session.dest_lat, lon=session.dest_lon)
    snapshot.started_at = _dt(state.started_at)
    snapshot.last_moved_at = _dt(state.last_moved_at)
    snapshot.arrived_at = _dt(state.arrived_at) or (
        session.ended_at if session.state == "finished" else None
    )
    if state.last_fix:
        snapshot.position = PositionOut(
            lat=state.last_fix["lat"],
            lon=state.last_fix["lon"],
            ele=state.last_fix.get("ele"),
            accuracy=state.last_fix.get("accuracy"),
            ts=_dt(state.last_fix["ts"]),
        )
    if state.remaining:
        total = session.route["dist"][-1] if session.route else None
        snapshot.progress = ProgressOut(
            done_m=state.progress_m if session.route else None,
            total_m=total,
            remaining_m=state.remaining["distance_m"],
            remaining_ascent_m=state.remaining["ascent_m"],
            remaining_descent_m=state.remaining["descent_m"],
            off_route=bool(session.route) and state.offset_m > OFF_ROUTE_M,
        )
    if state.eta:
        snapshot.eta = EtaOut(
            seconds=state.eta["seconds"],
            low_seconds=state.eta["low_seconds"],
            high_seconds=state.eta["high_seconds"],
            confidence=state.eta["confidence"],
            computed_at=_dt(state.eta["computed_at"]),
        )
    return snapshot


def route_out(route: Route) -> RouteOut:
    ascent, descent = route.climb_totals()
    return RouteOut(
        points=list(zip(route.lats, route.lons, route.eles, route.dists, strict=True)),
        distance_m=route.total_m,
        ascent_m=ascent,
        descent_m=descent,
        has_elevation=route.has_elevation,
    )
