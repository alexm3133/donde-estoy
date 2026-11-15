"""Viewer-side endpoints: no account, just the token from the share link."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.deps import Db, LiveHub, find_session_by_view_token
from app.models import STATE_ENDED, LiveSession, Position
from app.schemas import SessionView
from app.services.route import Route
from app.services.snapshot import build_snapshot, route_out

router = APIRouter(prefix="/api/view", tags=["viewer"])

#: The track is decimated to at most this many points for the initial load.
MAX_TRACK_POINTS = 1000
#: Idle connections get a ping this often (keeps proxies from closing them).
PING_INTERVAL_S = 25.0
#: WebSocket close code for "this link does not exist (any more)".
WS_CLOSE_NOT_FOUND = 4404


async def _load_track(db: Db, session: LiveSession) -> list[tuple[float, float]]:
    if session.state == STATE_ENDED:
        return []
    rows = (
        await db.execute(
            select(Position.lat, Position.lon)
            .where(Position.session_id == session.id)
            .order_by(Position.recorded_at, Position.id)
        )
    ).all()
    stride = len(rows) // MAX_TRACK_POINTS + 1
    track = [(lat, lon) for lat, lon in rows[::stride]]
    if rows and stride > 1 and track[-1] != tuple(rows[-1]):
        track.append(tuple(rows[-1]))
    return track


@router.get("/{token}", response_model=SessionView)
async def view_session(token: str, db: Db) -> SessionView:
    """Everything needed to draw the viewer page: state, route and track."""
    session = await find_session_by_view_token(db, token)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "link_not_found")
    view = SessionView(**build_snapshot(session).model_dump())
    if session.route:
        view.route = route_out(Route.from_dict(session.route))
    view.track = await _load_track(db, session)
    return view


@router.websocket("/{token}/ws")
async def view_session_live(websocket: WebSocket, token: str, db: Db, hub: LiveHub) -> None:
    """Live updates. Messages are JSON objects with a ``type``:

    * ``snapshot`` – ``data`` holds the new :class:`~app.schemas.Snapshot`
    * ``ping``     – keep-alive, ignore
    * ``expired``  – the session is gone; the socket closes right after
    """
    await websocket.accept()
    session = await find_session_by_view_token(db, token)
    if session is None:
        await websocket.close(code=WS_CLOSE_NOT_FOUND)
        return
    session_id = session.id
    first = {"type": "snapshot", "data": build_snapshot(session).model_dump(mode="json")}
    # Give the connection back to the pool: this handler may live for hours.
    await db.close()

    async def send_updates() -> None:
        await websocket.send_json(first)
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL_S)
            except TimeoutError:
                message = {"type": "ping"}
            await websocket.send_json(message)
            if message["type"] == "expired":
                await websocket.close(code=WS_CLOSE_NOT_FOUND)
                return

    async def wait_for_disconnect() -> None:
        # Viewers never send anything; we read only to notice them leaving.
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                await websocket.receive_text()

    # Subscribe *before* sending the first snapshot so no update can be missed.
    async with hub.subscribe(session_id) as queue:
        tasks = [asyncio.create_task(send_updates()), asyncio.create_task(wait_for_disconnect())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                    await task
