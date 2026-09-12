"""add cash-equivalent chart-account classification

Revision ID: e8b3c5d0f2a4
Revises: d7a2f4c9e1b3
Create Date: 2026-09-12 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8b3c5d0f2a4"
down_revision: str | Sequence[str] | None = "d7a2f4c9e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chart_accounts",
        sa.Column(
            "is_cash_equivalent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("chart_accounts", "is_cash_equivalent")
