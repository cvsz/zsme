"""enforce one bank reconciliation per payment

Revision ID: d7a2f4c9e1b3
Revises: c6f1a8d3e5b7
Create Date: 2026-09-12 20:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d7a2f4c9e1b3"
down_revision: str | Sequence[str] | None = "c6f1a8d3e5b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_bank_transactions_org_matched_payment",
        "bank_transactions",
        ["tenant_id", "organization_id", "matched_payment_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_bank_transactions_org_matched_payment",
        "bank_transactions",
        type_="unique",
    )
