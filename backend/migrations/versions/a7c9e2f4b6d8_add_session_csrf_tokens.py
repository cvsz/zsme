"""bind browser CSRF tokens to sessions

Revision ID: a7c9e2f4b6d8
Revises: f6b2d8e4a1c7
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e2f4b6d8"
down_revision: str | Sequence[str] | None = "f6b2d8e4a1c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "session_tokens",
        sa.Column("csrf_token_hash", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_tokens", "csrf_token_hash")
