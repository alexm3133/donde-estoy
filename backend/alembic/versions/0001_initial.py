"""Initial schema: sessions and positions.

Revision ID: 0001
Revises:
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("view_token_hash", sa.String(64), nullable=False),
        sa.Column("runner_token_hash", sa.String(64), nullable=False),
        sa.Column("runner_name", sa.String(40), nullable=False),
        sa.Column("activity", sa.String(10), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("stall_alert_minutes", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dest_lat", sa.Float, nullable=True),
        sa.Column("dest_lon", sa.Float, nullable=True),
        sa.Column("route", sa.JSON, nullable=True),
        sa.Column("tracker", sa.JSON, nullable=False),
    )
    op.create_index("ix_sessions_view_token_hash", "sessions", ["view_token_hash"], unique=True)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("ele", sa.Float, nullable=True),
        sa.Column("accuracy", sa.Float, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_positions_session_id", "positions", ["session_id"])


def downgrade() -> None:
    op.drop_table("positions")
    op.drop_table("sessions")
