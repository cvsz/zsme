"""guard one ledger posting per source

Revision ID: c2e7f9a1b3d5
Revises: b8d5e3f1a6c9
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "c2e7f9a1b3d5"
down_revision: str | Sequence[str] | None = "b8d5e3f1a6c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not context.is_offline_mode():
        duplicate = op.get_bind().execute(
            sa.text(
                """
                SELECT organization_id, source_type, source_id, COUNT(*) AS duplicate_count
                FROM journal_entries
                WHERE source_id IS NOT NULL
                GROUP BY organization_id, source_type, source_id
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()
        if duplicate is not None:
            raise RuntimeError(
                "cannot add journal source uniqueness: duplicate source lineage exists; "
                "review and reconcile journal_entries before rerunning the migration"
            )
    op.create_index(
        "uq_journal_entries_org_source",
        "journal_entries",
        ["organization_id", "source_type", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_id IS NOT NULL"),
        sqlite_where=sa.text("source_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_journal_entries_org_source", table_name="journal_entries")
