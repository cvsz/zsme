"""prevent one payment from reconciling multiple bank transactions

Revision ID: e7a9c3d5f1b2
Revises: c6f1a8d3e5b7
Create Date: 2026-09-12 21:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a9c3d5f1b2"
down_revision: str | Sequence[str] | None = "c6f1a8d3e5b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    duplicate_payment = op.get_bind().execute(
        sa.text(
            """
            SELECT matched_payment_id
            FROM bank_transactions
            WHERE matched_payment_id IS NOT NULL
            GROUP BY matched_payment_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if duplicate_payment is not None:
        raise RuntimeError(
            "cannot enforce one-to-one bank reconciliation: "
            f"payment {duplicate_payment} is matched to multiple bank transactions; "
            "review and correct reconciliation evidence before retrying the migration"
        )

    op.create_unique_constraint(
        "uq_bank_transactions_matched_payment",
        "bank_transactions",
        ["matched_payment_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_bank_transactions_matched_payment",
        "bank_transactions",
        type_="unique",
    )
