"""initial schema

Revision ID: 20260412_0001
Revises: None
Create Date: 2026-04-12 01:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260412_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sports",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "team_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("bookmaker", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias", "bookmaker", name="uq_alias_bookmaker"),
    )
    op.create_table(
        "leagues",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("sport_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=10), nullable=False),
        sa.Column("external_ids", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["sport_id"], ["sports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("league_id", sa.String(length=100), nullable=False),
        sa.Column("home_team", sa.String(length=200), nullable=False),
        sa.Column("away_team", sa.String(length=200), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("external_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("bookmaker", sa.String(length=50), nullable=False),
        sa.Column("market", sa.String(length=50), nullable=False),
        sa.Column("selection", sa.String(length=50), nullable=False),
        sa.Column("odds", sa.Float(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_odds_lookup",
        "odds_snapshots",
        ["match_id", "bookmaker", "market", "selection"],
        unique=False,
    )
    op.create_index(
        "ix_odds_scraped_at",
        "odds_snapshots",
        ["scraped_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_odds_scraped_at", table_name="odds_snapshots")
    op.drop_index("ix_odds_lookup", table_name="odds_snapshots")
    op.drop_table("odds_snapshots")
    op.drop_table("matches")
    op.drop_table("leagues")
    op.drop_table("team_aliases")
    op.drop_table("sports")
