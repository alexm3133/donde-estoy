"""Runner-side endpoints: create a session, post positions, finish, stop."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status

from app.db import utcnow
from app.deps import AppSettings, Db, LiveHub, RunnerSession
from app.models import STATE_ACTIVE, STATE_ENDED, STATE_FINISHED, LiveSession, Position
from app.schemas import (
    PositionBatch,
    PositionsAccepted,
    SessionCreate,
    SessionCreated,
    SessionView,
    Snapshot,
)
from app.security import hash_token, new_token
from app.services.cleanup import wipe_location_data
from app.services.hub import Hub
from app.services.route import Route, RouteError, build_route
from app.services.snapshot import build_snapshot, route_out
from app.services.tracker import Fix, Tracker, TrackerState

router = APIRouter(prefix="/api/sessions", tags=["runner"])

#: Fixes dated further in the future than this (after skew correction) are
#: pulled back to "now".
MAX_FUTURE_SKEW = timedelta(seconds=5)


def _publish(hub: Hub, session: LiveSession) -> Snapshot:
    snapshot = build_snapshot(session)
    hub.publish(session.id, {"type": "snapshot", "data": snapshot.model_dump(mode="json")})
    return snapshot


def _finish(session: LiveSession, now: datetime, grace_minutes: int) -> None:
    """Mark as arrived and shorten the link's life to the grace period."""
    session.state = STATE_FINISHED
    session.ended_at = now
    session.expires_at = min(session.expires_at, now + timedelta(minutes=grace_minutes))


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate, request: Request, db: Db, settings: AppSettings
) -> SessionCreated:
    """Start sharing. Returns the share link and the runner's secret token."""
    client_ip = request.client.host if request.client else "unknown"
    if not request.app.state.create_limiter.allow(client_ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_sessions")

    route: Route | None = None
    if body.route_points:
        try:
            route = build_route(body.route_points)
        except RouteError as exc:
            raise HTTPException(422, "route_too_short") from exc
        dest_lat, dest_lon = route.end
    else:
        dest_lat, dest_lon = body.destination.lat, body.destination.lon

    now = utcnow()
    hours = min(body.duration_hours or settings.default_session_hours, settings.max_session_hours)
    runner_token, view_token = new_token(), new_token()
    session = LiveSession(
        id=uuid.uuid4().hex,
        view_token_hash=hash_token(view_token),
        runner_token_hash=hash_token(runner_token),
        runner_name=body.runner_name,
        activity=body.activity,
        state=STATE_ACTIVE,
        stall_alert_minutes=body.stall_alert_minutes,
        created_at=now,
        expires_at=now + timedelta(hours=hours),
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        route=route.to_dict() if route else None,
        tracker={},
    )
    db.add(session)
    await db.commit()
    return SessionCreated(
        id=session.id,
        runner_token=runner_token,
        view_token=view_token,
        share_url=f"{settings.public_url.rstrip('/')}/s/{view_token}",
        expires_at=session.expires_at,
        snapshot=build_snapshot(session),
    )


@router.get("/{session_id}", response_model=SessionView)
async def get_own_session(session: RunnerSession) -> SessionView:
    """The runner's own view (used to resume after reloading the app)."""
    view = SessionView(**build_snapshot(session).model_dump())
    if session.route:
        view.route = route_out(Route.from_dict(session.route))
    return view


@router.post("/{session_id}/positions", response_model=PositionsAccepted)
async def post_positions(
    body: PositionBatch, session: RunnerSession, db: Db, hub: LiveHub, settings: AppSettings
) -> PositionsAccepted:
    """Report one or more GPS fixes (batches allow catching up after no signal)."""
    if session.state == STATE_ENDED:
        raise HTTPException(status.HTTP_410_GONE, "session_ended")
    if session.state == STATE_FINISHED:
        # Late buffered fixes after arrival: nothing to do, but not an error.
        return PositionsAccepted(accepted=0, snapshot=build_snapshot(session))

    now = utcnow()
    # The phone's clock may be off. If it told us what time it thinks it is,
    # shift its timestamps onto our clock.
    skew = (now - body.sent_at.astimezone(UTC)) if body.sent_at else timedelta(0)

    tracker = Tracker(
        TrackerState.from_dict(session.tracker),
        route=Route.from_dict(session.route) if session.route else None,
        destination=(session.dest_lat, session.dest_lon),
        activity=session.activity,
    )
    accepted = 0
    for item in sorted(body.positions, key=lambda p: p.ts):
        recorded_at = min(item.ts.astimezone(UTC) + skew, now + MAX_FUTURE_SKEW)
        fix = Fix(
            lat=item.lat,
            lon=item.lon,
            ts=recorded_at.timestamp(),
            ele=item.ele,
            accuracy=item.accuracy,
        )
        if not tracker.process(fix):
            continue
        accepted += 1
        db.add(
            Position(
                session_id=session.id,
                lat=item.lat,
                lon=item.lon,
                ele=item.ele,
                accuracy=item.accuracy,
                recorded_at=recorded_at,
            )
        )

    if accepted:
        session.tracker = tracker.state.to_dict()  # new dict => SQLAlchemy sees the change
        if tracker.state.arrived_at is not None:
            _finish(session, now, settings.finished_grace_minutes)
        await db.commit()
        snapshot = _publish(hub, session)
    else:
        snapshot = build_snapshot(session)
    return PositionsAccepted(accepted=accepted, snapshot=snapshot)


@router.post("/{session_id}/finish", response_model=Snapshot)
async def finish_session(
    session: RunnerSession, db: Db, hub: LiveHub, settings: AppSettings
) -> Snapshot:
    """Runner says "I have arrived" (when automatic detection did not fire)."""
    if session.state == STATE_ACTIVE:
        _finish(session, utcnow(), settings.finished_grace_minutes)
        await db.commit()
        return _publish(hub, session)
    return build_snapshot(session)


@router.post("/{session_id}/stop", response_model=Snapshot)
async def stop_sharing(session: RunnerSession, db: Db, hub: LiveHub) -> Snapshot:
    """Stop sharing immediately and erase all location data of the session."""
    if session.state != STATE_ENDED:
        await wipe_location_data(db, session, utcnow())
        await db.commit()
    return _publish(hub, session)
