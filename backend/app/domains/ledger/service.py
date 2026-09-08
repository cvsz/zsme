from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import (
    AuditEvent,
    ChartAccount,
    FiscalPeriod,
    IdempotencyRecord,
    JournalEntryRecord,
    JournalLineRecord,
)
from app.domains.ledger.schemas import (
    JournalEntryPage,
    JournalEntryRead,
    JournalLineRead,
    JournalPostCommand,
    JournalPostResult,
)


class DomainError(Exception):
    """A safe, expected domain failure that can be returned to an API client."""


def _entry_read(entry: JournalEntryRecord) -> JournalEntryRead:
    return JournalEntryRead(
        id=entry.id,
        tenant_id=entry.tenant_id,
        organization_id=entry.organization_id,
        fiscal_period_id=entry.fiscal_period_id,
        reference=entry.reference,
        journal_date=entry.journal_date,
        memo=entry.memo,
        status="posted",
        source_type=entry.source_type,
        source_id=entry.source_id,
        reversal_of_id=entry.reversal_of_id,
        posted_at=entry.posted_at,
        created_at=entry.created_at,
        lines=[
            JournalLineRead(
                id=line.id,
                line_no=line.line_no,
                account_code=line.account_code,
                debit=line.debit,
                credit=line.credit,
                memo=line.memo,
            )
            for line in entry.lines
        ],
        total_debit=sum((line.debit for line in entry.lines), start=Decimal("0.00")),
        total_credit=sum((line.credit for line in entry.lines), start=Decimal("0.00")),
    )


def list_journal_entries(
    db: Session,
    principal: Principal,
    *,
    reference: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JournalEntryPage:
    if principal.organization_id is None:
        raise DomainError("an organization is required for ledger operations")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise DomainError("from_date must be on or before to_date")

    filters = [
        JournalEntryRecord.tenant_id == principal.tenant_id,
        JournalEntryRecord.organization_id == principal.organization_id,
        JournalEntryRecord.status == "posted",
    ]
    if reference and reference.strip():
        filters.append(JournalEntryRecord.reference.ilike(f"%{reference.strip()}%"))
    if from_date is not None:
        filters.append(JournalEntryRecord.journal_date >= from_date)
    if to_date is not None:
        filters.append(JournalEntryRecord.journal_date <= to_date)

    total = db.scalar(select(func.count(JournalEntryRecord.id)).where(*filters)) or 0
    entries = list(
        db.scalars(
            select(JournalEntryRecord)
            .where(*filters)
            .order_by(
                JournalEntryRecord.journal_date.desc(),
                JournalEntryRecord.created_at.desc(),
                JournalEntryRecord.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    items = [_entry_read(entry) for entry in entries]
    next_offset = offset + len(items) if offset + len(items) < total else None
    return JournalEntryPage(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        next_offset=next_offset,
    )


def _request_hash(command: JournalPostCommand) -> str:
    serialized = json.dumps(
        command.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _existing_result(record: IdempotencyRecord) -> JournalPostResult:
    body = record.response_body
    return JournalPostResult(
        entry_id=UUID(str(body["entry_id"])),
        status="already_posted",
        total=body["total"],
        audit_event_id=UUID(str(body["audit_event_id"])),
    )


def post_journal_entry(
    db: Session,
    command: JournalPostCommand,
    principal: Principal,
    idempotency_key: str,
) -> JournalPostResult:
    if principal.organization_id is None:
        raise DomainError("an organization is required for ledger posting")
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 200:
        raise DomainError("a valid idempotency key is required")

    request_hash = _request_hash(command)
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.key == normalized_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise DomainError("idempotency key was reused with a different request")
        return _existing_result(existing)

    period = db.scalar(
        select(FiscalPeriod)
        .where(
            FiscalPeriod.tenant_id == principal.tenant_id,
            FiscalPeriod.organization_id == principal.organization_id,
            FiscalPeriod.start_date <= command.journal_date,
            FiscalPeriod.end_date >= command.journal_date,
        )
        .order_by(FiscalPeriod.start_date.desc())
    )
    if period is None:
        raise DomainError("no fiscal period covers the journal date")
    if period.status != "open":
        raise DomainError("period is locked")

    account_codes = {line.account_code for line in command.lines}
    accounts = db.scalars(
        select(ChartAccount).where(
            ChartAccount.tenant_id == principal.tenant_id,
            ChartAccount.organization_id == principal.organization_id,
            ChartAccount.code.in_(account_codes),
            ChartAccount.is_active.is_(True),
        )
    ).all()
    accounts_by_code = {account.code: account for account in accounts}
    missing_accounts = sorted(account_codes - accounts_by_code.keys())
    if missing_accounts:
        raise DomainError(f"unknown or inactive account: {', '.join(missing_accounts)}")
    control_accounts = sorted(
        account.code for account in accounts if account.is_control and account.code in account_codes
    )
    if control_accounts:
        raise DomainError(f"control account cannot receive posting: {', '.join(control_accounts)}")

    now = datetime.now(UTC)
    entry = JournalEntryRecord(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        fiscal_period_id=period.id,
        reference=command.reference,
        journal_date=command.journal_date,
        memo=command.memo,
        status="posted",
        source_type=command.source_type,
        source_id=command.source_id,
        idempotency_key=normalized_key,
        reversal_of_id=command.reversal_of_id,
        posted_at=now,
    )
    db.add(entry)
    db.flush()

    for line_no, line in enumerate(command.lines, start=1):
        db.add(
            JournalLineRecord(
                tenant_id=principal.tenant_id,
                organization_id=principal.organization_id,
                entry_id=entry.id,
                account_id=accounts_by_code[line.account_code].id,
                line_no=line_no,
                account_code=line.account_code,
                debit=line.debit,
                credit=line.credit,
                memo=line.memo,
            )
        )
    db.flush()

    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action="journal.post",
        entity_type="journal_entry",
        entity_id=entry.id,
        correlation_id=str(uuid4()),
        payload={
            "reference": entry.reference,
            "source_type": entry.source_type,
            "source_id": str(entry.source_id) if entry.source_id else None,
            "line_count": len(command.lines),
        },
    )
    db.add(audit)
    db.flush()

    total = sum((line.debit for line in command.lines), start=Decimal("0"))
    result = JournalPostResult(
        entry_id=entry.id,
        status="posted",
        total=total,
        audit_event_id=audit.id,
    )
    db.add(
        IdempotencyRecord(
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=normalized_key,
            operation="journal.post",
            request_hash=request_hash,
            response_status=201,
            response_body={
                "entry_id": str(result.entry_id),
                "total": str(result.total),
                "audit_event_id": str(result.audit_event_id),
            },
            resource_id=result.entry_id,
        )
    )
    db.flush()
    return result


def reverse_journal_entry(
    db: Session,
    entry_id: UUID,
    principal: Principal,
    idempotency_key: str,
) -> JournalPostResult:
    if principal.organization_id is None:
        raise DomainError("an organization is required for ledger reversal")
    original = db.scalar(
        select(JournalEntryRecord).where(
            JournalEntryRecord.id == entry_id,
            JournalEntryRecord.tenant_id == principal.tenant_id,
            JournalEntryRecord.organization_id == principal.organization_id,
        )
    )
    if original is None:
        raise DomainError("journal entry not found")
    if original.status != "posted":
        raise DomainError("only posted journal entries can be reversed")
    if original.reversal_of_id is not None:
        raise DomainError("a reversal entry cannot be reversed")
    if db.scalar(
        select(JournalEntryRecord.id).where(JournalEntryRecord.reversal_of_id == original.id)
    ):
        raise DomainError("journal entry has already been reversed")

    from app.domains.ledger.schemas import JournalLineInput

    command = JournalPostCommand(
        reference=f"REV-{original.reference}",
        memo=f"Reversal of {original.reference}",
        journal_date=original.journal_date,
        source_type="journal_reversal",
        source_id=original.id,
        reversal_of_id=original.id,
        lines=[
            JournalLineInput(
                account_code=line.account_code,
                debit=line.credit,
                credit=line.debit,
                memo=f"Reversal of line {line.line_no}",
            )
            for line in original.lines
        ],
    )
    return post_journal_entry(db, command, principal, idempotency_key)


__all__ = ["DomainError", "list_journal_entries", "post_journal_entry", "reverse_journal_entry"]
