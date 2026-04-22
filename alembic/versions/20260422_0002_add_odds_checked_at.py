"""add odds checked timestamp

Revision ID: 20260422_0002
Revises: 20260412_0001
Create Date: 2026-04-22 11:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260422_0002"
down_revision = "20260412_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("odds_snapshots", sa.Column("checked_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE odds_snapshots SET checked_at = scraped_at WHERE checked_at IS NULL")
    op.create_index("ix_odds_checked_at", "odds_snapshots", ["checked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_odds_checked_at", table_name="odds_snapshots")
    op.drop_column("odds_snapshots", "checked_at")
