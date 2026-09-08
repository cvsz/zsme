"""add audit query indexes

Revision ID: b8d5e3f1a6c9
Revises: a7c4d2e1f9b0
Create Date: 2026-09-08 14:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8d5e3f1a6c9"
down_revision: str | Sequence[str] | None = "a7c4d2e1f9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_events_org_created",
        "audit_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_org_action_created",
        "audit_events",
        ["organization_id", "action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_org_action_created", table_name="audit_events")
    op.drop_index("ix_audit_events_org_created", table_name="audit_events")
