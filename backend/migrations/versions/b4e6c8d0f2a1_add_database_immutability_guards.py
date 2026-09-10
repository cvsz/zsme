"""add database immutability guards for posted ledger data

Revision ID: b4e6c8d0f2a1
Revises: a7c9e2f4b6d8
Create Date: 2026-09-10 00:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4e6c8d0f2a1"
down_revision: str | Sequence[str] | None = "a7c9e2f4b6d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE FUNCTION zsme_reject_posted_journal_entry_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'posted' THEN
                RAISE EXCEPTION 'posted journal entries are immutable'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_immutable
        BEFORE UPDATE OR DELETE ON journal_entries
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_posted_journal_entry_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_posted_journal_line_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            entry_id uuid;
        BEGIN
            entry_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.entry_id ELSE OLD.entry_id END;
            IF EXISTS (
                SELECT 1 FROM journal_entries
                WHERE id = entry_id AND status = 'posted'
            ) THEN
                RAISE EXCEPTION 'posted journal entry lines are immutable'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_lines_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_posted_journal_line_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_assert_posted_journal_entry_balanced()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_entry_id uuid;
            line_count bigint;
            debit_total numeric;
            credit_total numeric;
        BEGIN
            IF TG_TABLE_NAME = 'journal_entries' THEN
                target_entry_id := NEW.id;
            ELSIF TG_OP = 'INSERT' THEN
                target_entry_id := NEW.entry_id;
            ELSE
                target_entry_id := OLD.entry_id;
            END IF;
            IF EXISTS (
                SELECT 1 FROM journal_entries
                WHERE journal_entries.id = target_entry_id AND status = 'posted'
            ) THEN
                SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                INTO line_count, debit_total, credit_total
                FROM journal_lines AS jl
                WHERE jl.entry_id = target_entry_id;
                IF line_count < 2 OR debit_total <> credit_total THEN
                    RAISE EXCEPTION 'posted journal entries must have balanced lines'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_journal_entries_balanced
        AFTER INSERT OR UPDATE OF status ON journal_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION zsme_assert_posted_journal_entry_balanced()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_journal_lines_balanced
        AFTER INSERT OR UPDATE OR DELETE ON journal_lines
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION zsme_assert_posted_journal_entry_balanced()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only'
                USING ERRCODE = 'restrict_violation';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_audit_event_mutation()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_lines_balanced ON journal_lines")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_balanced ON journal_entries")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_lines_immutable ON journal_lines")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_immutable ON journal_entries")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_audit_event_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_assert_posted_journal_entry_balanced()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_posted_journal_line_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_posted_journal_entry_mutation()")
