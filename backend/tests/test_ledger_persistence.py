from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import AuditEvent, JournalEntryRecord
from app.domains.ledger.schemas import JournalLineInput, JournalPostCommand
from app.domains.ledger.service import DomainError, post_journal_entry, reverse_journal_entry


@pytest.fixture
def principal(seeded_user) -> Principal:
    return Principal(
        session_id=uuid4(),
        user_id=seeded_user.id,
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        email=seeded_user.email,
        display_name=seeded_user.display_name,
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"accounting:write"}),
    )


@pytest.fixture
def balanced_command() -> JournalPostCommand:
    return JournalPostCommand(
        reference="AR-202609-0001",
        memo="Service invoice",
        journal_date=date(2026, 9, 8),
        source_type="invoice",
        lines=[
            JournalLineInput(account_code="1100", debit="1070.00"),
            JournalLineInput(account_code="4000", credit="1000.00"),
            JournalLineInput(account_code="2101", credit="70.00"),
        ],
    )


def test_posting_is_atomic_and_audited(
    db_session: Session, principal: Principal, balanced_command, ledger_ready
) -> None:
    result = post_journal_entry(db_session, balanced_command, principal, "post-001")

    entry = db_session.get(JournalEntryRecord, result.entry_id)
    audit = db_session.get(AuditEvent, result.audit_event_id)

    assert result.status == "posted"
    assert entry is not None
    assert len(entry.lines) == 3
    assert audit is not None
    assert audit.action == "journal.post"


def test_replaying_idempotency_key_does_not_duplicate_financial_effect(
    db_session: Session, principal: Principal, balanced_command, ledger_ready
) -> None:
    first = post_journal_entry(db_session, balanced_command, principal, "post-002")
    second = post_journal_entry(db_session, balanced_command, principal, "post-002")

    entry_count = db_session.scalar(
        select(func.count(JournalEntryRecord.id)).where(
            JournalEntryRecord.organization_id == principal.organization_id
        )
    )

    assert second.status == "already_posted"
    assert second.entry_id == first.entry_id
    assert entry_count == 1


def test_locked_period_rejects_posting(
    db_session: Session, principal: Principal, balanced_command, ledger_ready
) -> None:
    ledger_ready.status = "locked"
    db_session.commit()

    with pytest.raises(DomainError, match="period is locked"):
        post_journal_entry(db_session, balanced_command, principal, "post-003")


def test_reversal_balances_and_preserves_original(
    db_session: Session, principal: Principal, balanced_command, ledger_ready
) -> None:
    original = post_journal_entry(db_session, balanced_command, principal, "post-004")
    original_entry = db_session.get(JournalEntryRecord, original.entry_id)
    assert original_entry is not None
    original_memo = original_entry.memo

    reversal = reverse_journal_entry(db_session, original.entry_id, principal, "reverse-004")
    reversal_entry = db_session.get(JournalEntryRecord, reversal.entry_id)

    assert reversal.entry_id != original.entry_id
    assert reversal.status == "posted"
    assert reversal_entry is not None
    assert reversal_entry.reversal_of_id == original.entry_id
    assert sum(line.debit for line in reversal_entry.lines) == sum(
        line.credit for line in reversal_entry.lines
    )
    assert original_entry.memo == original_memo


def test_posted_entry_cannot_be_mutated_through_orm(
    db_session: Session, principal: Principal, balanced_command, ledger_ready
) -> None:
    result = post_journal_entry(db_session, balanced_command, principal, "post-005")
    entry = db_session.get(JournalEntryRecord, result.entry_id)
    assert entry is not None

    entry.memo = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        db_session.flush()
