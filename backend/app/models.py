"""Database models.

Two tables, on purpose: a sharing session and the GPS fixes received for it.
Nothing identifies a person beyond the display name they typed, and both
tokens are stored only as hashes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UTCDateTime

#: Session lifecycle.
STATE_ACTIVE = "active"  # sharing live position
STATE_FINISHED = "finished"  # runner arrived; link stays up for a grace period
STATE_ENDED = "ended"  # runner stopped sharing; location data already wiped


class LiveSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: SHA-256 of the token in the share link (lookup key for viewers).
    view_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: SHA-256 of the secret that lets the runner post positions / stop.
    runner_token_hash: Mapped[str] = mapped_column(String(64))

    runner_name: Mapped[str] = mapped_column(String(40))
    activity: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(10), default=STATE_ACTIVE)
    #: Viewers get a safety alert after this many minutes without movement.
    stall_alert_minutes: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    dest_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    dest_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: Processed route (see ``Route.to_dict``); NULL for tap-on-map sessions.
    route: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    #: Serialised ``TrackerState`` (progress, pace calibration, latest ETA).
    tracker: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Position(Base):
    """An accepted GPS fix. Deleted when the session ends or expires."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    ele: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime)
