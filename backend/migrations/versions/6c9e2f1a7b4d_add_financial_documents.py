"""add financial documents

Revision ID: 6c9e2f1a7b4d
Revises: 4b3f1e2a8c7d
Create Date: 2026-09-08 11:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6c9e2f1a7b4d"
down_revision: str | Sequence[str] | None = "4b3f1e2a8c7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_documents",
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("control_account_code", sa.String(length=32), nullable=False),
        sa.Column("tax_account_code", sa.String(length=32), nullable=True),
        sa.Column("memo", sa.String(length=500), nullable=True),
        sa.Column("subtotal", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
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
            "document_type IN ('sales_invoice', 'vendor_bill')",
            name="ck_financial_documents_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'posted', 'void')",
            name="ck_financial_documents_status",
        ),
        sa.CheckConstraint("issue_date <= due_date", name="ck_financial_documents_dates"),
        sa.CheckConstraint(
            "subtotal >= 0 AND tax_total >= 0 AND total >= 0",
            name="ck_financial_documents_totals_non_negative",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["partner_id"], ["business_partners.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "document_type",
            "document_number",
            name="uq_financial_documents_org_type_number",
        ),
    )
    op.create_index(
        op.f("ix_financial_documents_organization_id"),
        "financial_documents",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_documents_tenant_id"),
        "financial_documents",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_financial_documents_org_type_status",
        "financial_documents",
        ["organization_id", "document_type", "status"],
        unique=False,
    )

    op.create_table(
        "financial_document_lines",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("net_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("account_code", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_financial_document_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_financial_document_lines_unit_price"),
        sa.CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100", name="ck_financial_document_lines_tax_rate"
        ),
        sa.CheckConstraint(
            "net_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0",
            name="ck_financial_document_lines_amounts_non_negative",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["financial_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "line_no", name="uq_financial_document_lines_document_line_no"
        ),
    )
    op.create_index(
        op.f("ix_financial_document_lines_organization_id"),
        "financial_document_lines",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_document_lines_tenant_id"),
        "financial_document_lines",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_financial_document_lines_document_id",
        "financial_document_lines",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_financial_document_lines_document_id", table_name="financial_document_lines")
    op.drop_index(op.f("ix_financial_document_lines_tenant_id"), table_name="financial_document_lines")
    op.drop_index(
        op.f("ix_financial_document_lines_organization_id"), table_name="financial_document_lines"
    )
    op.drop_table("financial_document_lines")
    op.drop_index("ix_financial_documents_org_type_status", table_name="financial_documents")
    op.drop_index(op.f("ix_financial_documents_tenant_id"), table_name="financial_documents")
    op.drop_index(op.f("ix_financial_documents_organization_id"), table_name="financial_documents")
    op.drop_table("financial_documents")
