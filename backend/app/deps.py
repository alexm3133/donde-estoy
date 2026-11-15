"""FastAPI dependencies shared by the routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from .config import Settings
from .db import utcnow
from .models import LiveSession
from .security import hash_token, token_matches
from .services.hub import Hub


# ``HTTPConnection`` is the common base of Request and WebSocket, so these
# work for both kinds of endpoint.
async def get_db(conn: HTTPConnection) -> AsyncIterator[AsyncSession]:
    async with conn.app.state.sessionmaker() as db:
        yield db


def get_settings(conn: HTTPConnection) -> Settings:
    return conn.app.state.settings


def get_hub(conn: HTTPConnection) -> Hub:
    return conn.app.state.hub


Db = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
LiveHub = Annotated[Hub, Depends(get_hub)]


async def find_session_by_view_token(db: AsyncSession, token: str) -> LiveSession | None:
    """Look up a live (non-expired) session from the token in a share link."""
    session = (
        await db.execute(
            select(LiveSession).where(LiveSession.view_token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    if session is None or session.expires_at <= utcnow():
        return None
    return session


async def runner_session(
    session_id: str,
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> LiveSession:
    """The session named in the URL, if the caller holds its runner token.

    The row is locked (``FOR UPDATE`` on PostgreSQL) so that two position
    batches for the same session cannot interleave their tracker updates.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_runner_token")
    session = (
        await db.execute(select(LiveSession).where(LiveSession.id == session_id).with_for_update())
    ).scalar_one_or_none()
    # Same error whether the session is unknown, expired or the token is wrong:
    # do not reveal which session ids exist.
    if (
        session is None
        or session.expires_at <= utcnow()
        or not token_matches(token, session.runner_token_hash)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session_not_found")
    return session


RunnerSession = Annotated[LiveSession, Depends(runner_session)]
