"""Privacy housekeeping: wiping location data and purging expired sessions."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import STATE_ENDED, LiveSession, Position

from .hub import Hub

logger = logging.getLogger(__name__)


async def wipe_location_data(db: AsyncSession, session: LiveSession, now: datetime) -> None:
    """Runner pressed "stop sharing": forget where they were, right now.

    The row itself survives (without any location) until it expires, only so
    that people holding the link see "sharing has ended" instead of an error.
    """
    await db.execute(delete(Position).where(Position.session_id == session.id))
    session.state = STATE_ENDED
    session.ended_at = now
    session.route = None
    session.tracker = {}
    session.dest_lat = None
    session.dest_lon = None


async def purge_expired(
    sessionmaker: async_sessionmaker[AsyncSession], hub: Hub, now: datetime | None = None
) -> int:
    """Delete every expired session and its positions. Returns how many."""
    now = now or utcnow()
    async with sessionmaker() as db:
        expired = (
            (await db.execute(select(LiveSession.id).where(LiveSession.expires_at <= now)))
            .scalars()
            .all()
        )
        if not expired:
            return 0
        # Explicit delete of positions: do not rely on FK cascades being
        # enabled (SQLite has them off by default).
        await db.execute(delete(Position).where(Position.session_id.in_(expired)))
        await db.execute(delete(LiveSession).where(LiveSession.id.in_(expired)))
        await db.commit()
    for session_id in expired:
        hub.publish(session_id, {"type": "expired"})
    return len(expired)


async def cleanup_loop(
    sessionmaker: async_sessionmaker[AsyncSession], hub: Hub, interval_seconds: float
) -> None:
    """Background task: purge expired sessions forever."""
    while True:
        try:
            purged = await purge_expired(sessionmaker, hub)
            if purged:
                logger.info("purged %d expired session(s)", purged)
        except Exception:  # keep the loop alive whatever happens
            logger.exception("cleanup failed")
        await asyncio.sleep(interval_seconds)
