"""add effective-dated tax rate rules

Revision ID: 9f6b3c1d8e2a
Revises: 8e5a2b7c1d9f
Create Date: 2026-09-08 13:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f6b3c1d8e2a"
down_revision: str | Sequence[str] | None = "8e5a2b7c1d9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tax_rate_rules",
        sa.Column("tax_type", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "tax_type IN ('vat', 'withholding')", name="ck_tax_rate_rules_type"
        ),
        sa.CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_rate_rules_rate"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from <= effective_to",
            name="ck_tax_rate_rules_dates",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "tax_type",
            "code",
            "effective_from",
            name="uq_tax_rate_rules_org_type_code_from",
        ),
    )
    op.create_index(
        op.f("ix_tax_rate_rules_organization_id"),
        "tax_rate_rules",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tax_rate_rules_tenant_id"), "tax_rate_rules", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_tax_rate_rules_org_type_effective",
        "tax_rate_rules",
        ["organization_id", "tax_type", "effective_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tax_rate_rules_org_type_effective", table_name="tax_rate_rules")
    op.drop_index(op.f("ix_tax_rate_rules_tenant_id"), table_name="tax_rate_rules")
    op.drop_index(op.f("ix_tax_rate_rules_organization_id"), table_name="tax_rate_rules")
    op.drop_table("tax_rate_rules")
