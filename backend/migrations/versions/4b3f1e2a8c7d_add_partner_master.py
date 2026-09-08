"""add partner master

Revision ID: 4b3f1e2a8c7d
Revises: f27b9d5a4dc3
Create Date: 2026-09-08 10:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b3f1e2a8c7d"
down_revision: str | Sequence[str] | None = "f27b9d5a4dc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_partners",
        sa.Column("partner_code", sa.String(length=64), nullable=False),
        sa.Column("partner_type", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=250), nullable=False),
        sa.Column("legal_name", sa.String(length=250), nullable=True),
        sa.Column("tax_id", sa.String(length=32), nullable=True),
        sa.Column("tax_branch", sa.String(length=20), server_default="00000", nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "credit_limit",
            sa.Numeric(precision=18, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "partner_type IN ('customer', 'vendor', 'both')",
            name="ck_business_partners_type",
        ),
        sa.CheckConstraint("credit_limit >= 0", name="ck_business_partners_credit_limit"),
        sa.CheckConstraint("payment_terms_days >= 0", name="ck_business_partners_payment_terms"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "partner_code", name="uq_business_partners_org_code"
        ),
    )
    op.create_index(
        op.f("ix_business_partners_organization_id"),
        "business_partners",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_partners_tenant_id"), "business_partners", ["tenant_id"], unique=False
    )

    op.create_table(
        "partner_addresses",
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("address_type", sa.String(length=20), server_default="other", nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("address_line1", sa.String(length=250), nullable=False),
        sa.Column("address_line2", sa.String(length=250), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("province", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country_code", sa.String(length=2), server_default="TH", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "address_type IN ('registered', 'billing', 'shipping', 'other')",
            name="ck_partner_addresses_type",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["partner_id"], ["business_partners.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_partner_addresses_organization_id"),
        "partner_addresses",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_addresses_tenant_id"), "partner_addresses", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_addresses_tenant_id"), table_name="partner_addresses")
    op.drop_index(op.f("ix_partner_addresses_organization_id"), table_name="partner_addresses")
    op.drop_table("partner_addresses")
    op.drop_index(op.f("ix_business_partners_tenant_id"), table_name="business_partners")
    op.drop_index(
        op.f("ix_business_partners_organization_id"), table_name="business_partners"
    )
    op.drop_table("business_partners")
