"""add accounting master controls

Revision ID: 7d4f1a2c9b8e
Revises: 6c9e2f1a7b4d
Create Date: 2026-09-08 11:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d4f1a2c9b8e"
down_revision: str | Sequence[str] | None = "6c9e2f1a7b4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chart_accounts",
        sa.Column("parent_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "chart_accounts",
        sa.Column("is_control", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "chart_accounts",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_foreign_key(
        "fk_chart_accounts_parent_id",
        "chart_accounts",
        "chart_accounts",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_chart_accounts_parent_id", "chart_accounts", ["parent_id"], unique=False)
    op.create_check_constraint(
        "ck_chart_accounts_type",
        "chart_accounts",
        "account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')",
    )

    op.add_column(
        "fiscal_periods",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "fiscal_periods",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("fiscal_periods", "version")
    op.drop_column("fiscal_periods", "locked_at")
    op.drop_constraint("ck_chart_accounts_type", "chart_accounts", type_="check")
    op.drop_index("ix_chart_accounts_parent_id", table_name="chart_accounts")
    op.drop_constraint("fk_chart_accounts_parent_id", "chart_accounts", type_="foreignkey")
    op.drop_column("chart_accounts", "version")
    op.drop_column("chart_accounts", "is_control")
    op.drop_column("chart_accounts", "parent_id")
