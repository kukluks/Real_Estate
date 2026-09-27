"""Initial schema for sources and raw_posts

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _unique_constraint_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {uc["name"] for uc in inspect(bind).get_unique_constraints(table) if uc.get("name")}


def upgrade() -> None:
    # --- sources ---
    if not _has_table("sources"):
        op.create_table(
            "sources",
            sa.Column("source_type", sa.String(length=100), nullable=False),
            sa.Column("profile_username", sa.String(length=255), nullable=False),
            sa.Column("profile_url", sa.String(length=500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("added_by_chat_id", sa.String(length=64), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "profile_username",
                "added_by_chat_id",
                name="uq_source_profile_owner",
            ),
        )
        op.create_index(
            "ix_sources_added_by_chat_id",
            "sources",
            ["added_by_chat_id"],
            unique=False,
        )
    else:
        cols = _column_names("sources")
        if "added_by_chat_id" not in cols:
            op.add_column(
                "sources",
                sa.Column("added_by_chat_id", sa.String(length=64), nullable=True),
            )
            op.create_index(
                "ix_sources_added_by_chat_id",
                "sources",
                ["added_by_chat_id"],
                unique=False,
            )

        # Старый unique только на profile_username → составной unique
        uq_names = _unique_constraint_names("sources")
        if "sources_profile_username_key" in uq_names:
            op.drop_constraint("sources_profile_username_key", "sources", type_="unique")
        if "uq_source_profile_owner" not in uq_names:
            op.create_unique_constraint(
                "uq_source_profile_owner",
                "sources",
                ["profile_username", "added_by_chat_id"],
            )

    # --- raw_posts ---
    if not _has_table("raw_posts"):
        op.create_table(
            "raw_posts",
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("profile_username", sa.String(length=255), nullable=False),
            sa.Column("external_id", sa.String(length=100), nullable=False),
            sa.Column("post_url", sa.String(length=500), nullable=False),
            sa.Column("post_title", sa.Text(), nullable=True),
            sa.Column("raw_caption", sa.Text(), nullable=True),
            sa.Column("media_urls", sa.Text(), nullable=True),
            sa.Column("media_paths", sa.Text(), nullable=True),
            sa.Column("thumbnail_url", sa.Text(), nullable=True),
            sa.Column("thumbnail_path", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "fetched_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("ai_status", sa.String(length=50), nullable=False),
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("external_id"),
            sa.UniqueConstraint("post_url"),
        )


def downgrade() -> None:
    if _has_table("raw_posts"):
        op.drop_table("raw_posts")
    if _has_table("sources"):
        op.drop_index("ix_sources_added_by_chat_id", table_name="sources")
        op.drop_table("sources")
