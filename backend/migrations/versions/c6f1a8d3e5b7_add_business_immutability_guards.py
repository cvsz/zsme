"""add database immutability guards for posted business records

Revision ID: c6f1a8d3e5b7
Revises: b4e6c8d0f2a1
Create Date: 2026-09-10 00:45:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c6f1a8d3e5b7"
down_revision: str | Sequence[str] | None = "b4e6c8d0f2a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE FUNCTION zsme_reject_posted_financial_document_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'posted' THEN
                RAISE EXCEPTION 'posted financial documents are immutable'
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
        CREATE TRIGGER trg_financial_documents_immutable
        BEFORE UPDATE OR DELETE ON financial_documents
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_posted_financial_document_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_posted_financial_document_line_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_document_id uuid;
            document_status text;
        BEGIN
            target_document_id := CASE
                WHEN TG_OP = 'INSERT' THEN NEW.document_id
                ELSE OLD.document_id
            END;
            SELECT status
            INTO document_status
            FROM financial_documents
            WHERE id = target_document_id;
            IF document_status = 'posted' THEN
                RAISE EXCEPTION 'posted financial document lines are immutable'
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
        CREATE TRIGGER trg_financial_document_lines_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON financial_document_lines
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_posted_financial_document_line_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_posted_payment_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'posted' THEN
                RAISE EXCEPTION 'posted payments are immutable'
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
        CREATE TRIGGER trg_payment_records_immutable
        BEFORE UPDATE OR DELETE ON payment_records
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_posted_payment_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_posted_payment_allocation_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_payment_id uuid;
            payment_status text;
        BEGIN
            target_payment_id := CASE
                WHEN TG_OP = 'INSERT' THEN NEW.payment_id
                ELSE OLD.payment_id
            END;
            SELECT status
            INTO payment_status
            FROM payment_records
            WHERE id = target_payment_id;
            IF payment_status = 'posted' THEN
                RAISE EXCEPTION 'posted payment allocations are immutable'
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
        CREATE TRIGGER trg_payment_allocations_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON payment_allocations
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_posted_payment_allocation_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_committed_bank_import_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'committed' THEN
                RAISE EXCEPTION 'committed bank import batches are immutable'
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
        CREATE TRIGGER trg_bank_import_batches_immutable
        BEFORE UPDATE OR DELETE ON bank_import_batches
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_committed_bank_import_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION zsme_reject_bank_transaction_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'imported bank transactions are immutable'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF NEW.bank_account_id IS DISTINCT FROM OLD.bank_account_id
                OR NEW.import_batch_id IS DISTINCT FROM OLD.import_batch_id
                OR NEW.external_id IS DISTINCT FROM OLD.external_id
                OR NEW.transaction_date IS DISTINCT FROM OLD.transaction_date
                OR NEW.value_date IS DISTINCT FROM OLD.value_date
                OR NEW.description IS DISTINCT FROM OLD.description
                OR NEW.reference IS DISTINCT FROM OLD.reference
                OR NEW.amount IS DISTINCT FROM OLD.amount THEN
                RAISE EXCEPTION 'imported bank transaction source fields are immutable'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF OLD.status = 'reconciled' THEN
                RAISE EXCEPTION 'reconciled bank transactions are immutable'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF NEW.status = 'unmatched'
                AND (NEW.matched_payment_id IS NOT NULL OR NEW.reconciled_at IS NOT NULL) THEN
                RAISE EXCEPTION 'an unmatched bank transaction cannot have a reconciliation match'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status = 'reconciled'
                AND (NEW.matched_payment_id IS NULL OR NEW.reconciled_at IS NULL) THEN
                RAISE EXCEPTION
                    'a reconciled bank transaction requires a payment match and timestamp'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bank_transactions_immutable
        BEFORE UPDATE OR DELETE ON bank_transactions
        FOR EACH ROW
        EXECUTE FUNCTION zsme_reject_bank_transaction_mutation()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP TRIGGER IF EXISTS trg_bank_transactions_immutable ON bank_transactions")
    op.execute("DROP TRIGGER IF EXISTS trg_bank_import_batches_immutable ON bank_import_batches")
    op.execute("DROP TRIGGER IF EXISTS trg_payment_allocations_immutable ON payment_allocations")
    op.execute("DROP TRIGGER IF EXISTS trg_payment_records_immutable ON payment_records")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_financial_document_lines_immutable ON financial_document_lines"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_financial_documents_immutable ON financial_documents")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_bank_transaction_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_committed_bank_import_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_posted_payment_allocation_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_posted_payment_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_posted_financial_document_line_mutation()")
    op.execute("DROP FUNCTION IF EXISTS zsme_reject_posted_financial_document_mutation()")
