"""add bank account imports and reconciliation

Revision ID: a7c4d2e1f9b0
Revises: 9f6b3c1d8e2a
Create Date: 2026-09-08 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c4d2e1f9b0"
down_revision: str | Sequence[str] | None = "9f6b3c1d8e2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("bank_name", sa.String(length=200), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("ledger_account_code", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "account_code", name="uq_bank_accounts_org_code"),
    )
    op.create_index(
        op.f("ix_bank_accounts_organization_id"),
        "bank_accounts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_accounts_tenant_id"), "bank_accounts", ["tenant_id"], unique=False
    )

    op.create_table(
        "bank_import_batches",
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("batch_reference", sa.String(length=150), nullable=False),
        sa.Column("source_name", sa.String(length=250), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="staged", nullable=False),
        sa.Column("transaction_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('staged', 'committed', 'failed')",
            name="ck_bank_import_batches_status",
        ),
        sa.CheckConstraint("transaction_count >= 0", name="ck_bank_import_batches_count"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "bank_account_id",
            "batch_reference",
            name="uq_bank_import_batches_org_account_reference",
        ),
    )
    op.create_index(
        op.f("ix_bank_import_batches_organization_id"),
        "bank_import_batches",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_import_batches_tenant_id"),
        "bank_import_batches",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_bank_import_batches_account_created",
        "bank_import_batches",
        ["bank_account_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "bank_transactions",
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=150), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="unmatched", nullable=False),
        sa.Column("matched_payment_id", sa.Uuid(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('unmatched', 'reconciled')",
            name="ck_bank_transactions_status",
        ),
        sa.CheckConstraint("amount <> 0", name="ck_bank_transactions_amount_nonzero"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["import_batch_id"], ["bank_import_batches.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["matched_payment_id"], ["payment_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bank_account_id",
            "external_id",
            name="uq_bank_transactions_account_external_id",
        ),
    )
    op.create_index(
        op.f("ix_bank_transactions_organization_id"),
        "bank_transactions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_transactions_tenant_id"),
        "bank_transactions",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_bank_transactions_account_status_date",
        "bank_transactions",
        ["bank_account_id", "status", "transaction_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_transactions_account_status_date", table_name="bank_transactions"
    )
    op.drop_index(op.f("ix_bank_transactions_tenant_id"), table_name="bank_transactions")
    op.drop_index(op.f("ix_bank_transactions_organization_id"), table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index("ix_bank_import_batches_account_created", table_name="bank_import_batches")
    op.drop_index(op.f("ix_bank_import_batches_tenant_id"), table_name="bank_import_batches")
    op.drop_index(
        op.f("ix_bank_import_batches_organization_id"), table_name="bank_import_batches"
    )
    op.drop_table("bank_import_batches")
    op.drop_index(op.f("ix_bank_accounts_tenant_id"), table_name="bank_accounts")
    op.drop_index(op.f("ix_bank_accounts_organization_id"), table_name="bank_accounts")
    op.drop_table("bank_accounts")
