"""add missing platform organization foreign keys

Revision ID: e5a1c7d9f2b4
Revises: d4f8a2c6e1b7
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5a1c7d9f2b4"
down_revision: str | Sequence[str] | None = "d4f8a2c6e1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_idempotency_records_organization_id",
        "idempotency_records",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_audit_events_organization_id",
        "audit_events",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_audit_events_organization_id", "audit_events", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_idempotency_records_organization_id",
        "idempotency_records",
        type_="foreignkey",
    )
