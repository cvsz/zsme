"""enforce tenant-scoped foreign-key relationships

Revision ID: f6b2d8e4a1c7
Revises: e5a1c7d9f2b4
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "f6b2d8e4a1c7"
down_revision: str | Sequence[str] | None = "e5a1c7d9f2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPED_TABLES = (
    "organizations",
    "users",
    "roles",
    "session_tokens",
    "idempotency_records",
    "audit_events",
    "chart_accounts",
    "fiscal_periods",
    "journal_entries",
    "journal_lines",
    "business_partners",
    "partner_addresses",
    "financial_documents",
    "financial_document_lines",
    "payment_records",
    "payment_allocations",
    "tax_rate_rules",
    "bank_accounts",
    "bank_import_batches",
    "bank_transactions",
)

_ORGANIZATION_SCOPES = tuple(
    (table, "organizations", ("tenant_id", "organization_id"), ("tenant_id", "id"))
    for table in _SCOPED_TABLES
    if table not in {
        "organizations",
        "users",
        "roles",
        "session_tokens",
        "idempotency_records",
        "audit_events",
    }
)

_CROSS_SCOPE_REFERENCES = (
    ("users", "organizations", ("tenant_id", "organization_id"), ("tenant_id", "id")),
    ("user_roles", "users", ("tenant_id", "user_id"), ("tenant_id", "id")),
    ("user_roles", "roles", ("tenant_id", "role_id"), ("tenant_id", "id")),
    ("session_tokens", "users", ("tenant_id", "user_id"), ("tenant_id", "id")),
    ("audit_events", "users", ("tenant_id", "actor_user_id"), ("tenant_id", "id")),
    ("idempotency_records", "organizations", ("tenant_id", "organization_id"), ("tenant_id", "id")),
    ("chart_accounts", "chart_accounts", ("tenant_id", "parent_id"), ("tenant_id", "id")),
    ("journal_entries", "fiscal_periods", ("tenant_id", "fiscal_period_id"), ("tenant_id", "id")),
    ("journal_entries", "journal_entries", ("tenant_id", "reversal_of_id"), ("tenant_id", "id")),
    ("journal_lines", "journal_entries", ("tenant_id", "entry_id"), ("tenant_id", "id")),
    ("journal_lines", "chart_accounts", ("tenant_id", "account_id"), ("tenant_id", "id")),
    ("partner_addresses", "business_partners", ("tenant_id", "partner_id"), ("tenant_id", "id")),
    ("financial_documents", "business_partners", ("tenant_id", "partner_id"), ("tenant_id", "id")),
    (
        "financial_documents",
        "journal_entries",
        ("tenant_id", "ledger_entry_id"),
        ("tenant_id", "id"),
    ),
    (
        "financial_document_lines",
        "financial_documents",
        ("tenant_id", "document_id"),
        ("tenant_id", "id"),
    ),
    ("payment_records", "business_partners", ("tenant_id", "partner_id"), ("tenant_id", "id")),
    ("payment_records", "journal_entries", ("tenant_id", "ledger_entry_id"), ("tenant_id", "id")),
    ("payment_allocations", "payment_records", ("tenant_id", "payment_id"), ("tenant_id", "id")),
    (
        "payment_allocations",
        "financial_documents",
        ("tenant_id", "document_id"),
        ("tenant_id", "id"),
    ),
    ("bank_import_batches", "bank_accounts", ("tenant_id", "bank_account_id"), ("tenant_id", "id")),
    ("bank_transactions", "bank_accounts", ("tenant_id", "bank_account_id"), ("tenant_id", "id")),
    (
        "bank_transactions",
        "bank_import_batches",
        ("tenant_id", "import_batch_id"),
        ("tenant_id", "id"),
    ),
    (
        "bank_transactions",
        "payment_records",
        ("tenant_id", "matched_payment_id"),
        ("tenant_id", "id"),
    ),
)


def upgrade() -> None:
    _assert_no_orphans((*_ORGANIZATION_SCOPES, *_CROSS_SCOPE_REFERENCES))
    for table in _SCOPED_TABLES:
        op.create_unique_constraint(
            f"uq_{table}_tenant_id",
            table,
            ["tenant_id", "id"],
        )
    for index, (child, parent, child_columns, parent_columns) in enumerate(
        (*_ORGANIZATION_SCOPES, *_CROSS_SCOPE_REFERENCES), start=1
    ):
        op.create_foreign_key(
            f"fk_tenant_scope_{index}_{child}_{child_columns[-1]}",
            child,
            parent,
            list(child_columns),
            list(parent_columns),
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for index, (child, _parent, child_columns, _parent_columns) in reversed(
        list(enumerate((*_ORGANIZATION_SCOPES, *_CROSS_SCOPE_REFERENCES), start=1))
    ):
        op.drop_constraint(
            f"fk_tenant_scope_{index}_{child}_{child_columns[-1]}",
            child,
            type_="foreignkey",
        )
    for table in reversed(_SCOPED_TABLES):
        op.drop_constraint(f"uq_{table}_tenant_id", table, type_="unique")


def _assert_no_orphans(
    references: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]
) -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    for child, parent, child_columns, parent_columns in references:
        child_join = " AND ".join(
            f"child.{child_column} = parent.{parent_column}"
            for child_column, parent_column in zip(child_columns, parent_columns, strict=True)
        )
        non_null = " AND ".join(f"child.{column} IS NOT NULL" for column in child_columns)
        orphan = connection.execute(
            sa.text(
                f"SELECT 1 FROM {child} AS child "
                f"LEFT JOIN {parent} AS parent ON {child_join} "
                f"WHERE {non_null} AND parent.id IS NULL LIMIT 1"
            )
        ).first()
        if orphan is not None:
            raise RuntimeError(
                f"cannot enforce tenant-scoped foreign key {child}.{child_columns[-1]} -> "
                f"{parent}.id: existing tenant mismatch or orphaned reference"
            )
