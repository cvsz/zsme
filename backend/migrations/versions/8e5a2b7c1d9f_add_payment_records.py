"""add receipt and disbursement records

Revision ID: 8e5a2b7c1d9f
Revises: 7d4f1a2c9b8e
Create Date: 2026-09-08 12:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8e5a2b7c1d9f"
down_revision: str | Sequence[str] | None = "7d4f1a2c9b8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_records",
        sa.Column("payment_type", sa.String(length=20), nullable=False),
        sa.Column("payment_number", sa.String(length=100), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("cash_account_code", sa.String(length=32), nullable=False),
        sa.Column("unapplied_account_code", sa.String(length=32), nullable=True),
        sa.Column("memo", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("ledger_entry_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "payment_type IN ('receipt', 'disbursement')", name="ck_payment_records_type"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'posted', 'void')", name="ck_payment_records_status"
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_records_amount"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["partner_id"], ["business_partners.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "payment_type",
            "payment_number",
            name="uq_payment_records_org_type_number",
        ),
    )
    op.create_index(
        op.f("ix_payment_records_organization_id"),
        "payment_records",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_records_tenant_id"), "payment_records", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_payment_records_org_type_status",
        "payment_records",
        ["organization_id", "payment_type", "status"],
        unique=False,
    )

    op.create_table(
        "payment_allocations",
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocations_amount"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["financial_documents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_id", "document_id", name="uq_payment_allocations_payment_document"
        ),
    )
    op.create_index(
        op.f("ix_payment_allocations_organization_id"),
        "payment_allocations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_allocations_tenant_id"),
        "payment_allocations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_allocations_document_id",
        "payment_allocations",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_allocations_document_id", table_name="payment_allocations")
    op.drop_index(op.f("ix_payment_allocations_tenant_id"), table_name="payment_allocations")
    op.drop_index(op.f("ix_payment_allocations_organization_id"), table_name="payment_allocations")
    op.drop_table("payment_allocations")
    op.drop_index("ix_payment_records_org_type_status", table_name="payment_records")
    op.drop_index(op.f("ix_payment_records_tenant_id"), table_name="payment_records")
    op.drop_index(op.f("ix_payment_records_organization_id"), table_name="payment_records")
    op.drop_table("payment_records")
