"""add scrape runs

Revision ID: 20260424_0003
Revises: 20260422_0002
Create Date: 2026-04-24 13:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260424_0003"
down_revision = "20260422_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bookmaker", sa.String(length=50), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("matches_found", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("odds_saved", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scrape_runs_bookmaker_started_at",
        "scrape_runs",
        ["bookmaker", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_scrape_runs_bookmaker_finished_at",
        "scrape_runs",
        ["bookmaker", "finished_at"],
        unique=False,
    )
    op.create_index(
        "ix_scrape_runs_bookmaker_status_finished_at",
        "scrape_runs",
        ["bookmaker", "status", "finished_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scrape_runs_bookmaker_status_finished_at", table_name="scrape_runs")
    op.drop_index("ix_scrape_runs_bookmaker_finished_at", table_name="scrape_runs")
    op.drop_index("ix_scrape_runs_bookmaker_started_at", table_name="scrape_runs")
    op.drop_table("scrape_runs")
