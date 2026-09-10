"""add durable login throttles

Revision ID: d4f8a2c6e1b7
Revises: c2e7f9a1b3d5
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f8a2c6e1b7"
down_revision: str | Sequence[str] | None = "c2e7f9a1b3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("bucket_key", sa.String(length=128), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_login_throttles_failures"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_key", name="uq_login_throttles_bucket"),
    )


def downgrade() -> None:
    op.drop_table("login_throttles")
