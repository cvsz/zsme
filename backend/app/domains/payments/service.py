from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.db.models import (
    AuditEvent,
    FinancialDocument,
    IdempotencyRecord,
    PaymentAllocation,
    PaymentRecord,
)
from app.domains.ledger.schemas import JournalLineInput, JournalPostCommand
from app.domains.ledger.service import DomainError as LedgerDomainError
from app.domains.ledger.service import post_journal_entry
from app.domains.payments.schemas import PaymentCreate, PaymentType

MONEY = Decimal("0.01")


class PaymentDomainError(Exception):
    """A safe, expected payment-domain failure."""


@dataclass(frozen=True)
class PaymentMutationResult:
    payment: PaymentRecord
    replayed: bool = False


def _hash(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _key(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise PaymentDomainError("a valid idempotency key is required")
    return normalized


def _org(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise PaymentDomainError("an organization is required for payment operations")
    return principal.organization_id


def _payment_query(principal: Principal, payment_type: PaymentType):
    return (
        select(PaymentRecord)
        .options(selectinload(PaymentRecord.allocations))
        .where(
            PaymentRecord.tenant_id == principal.tenant_id,
            PaymentRecord.organization_id == principal.organization_id,
            PaymentRecord.payment_type == payment_type,
        )
    )


def _get_payment(
    db: Session, payment_id: UUID, principal: Principal, payment_type: PaymentType
) -> PaymentRecord:
    _org(principal)
    payment = db.scalar(
        _payment_query(principal, payment_type).where(PaymentRecord.id == payment_id)
    )
    if payment is None:
        raise PaymentDomainError("payment not found")
    return payment


def _record(db: Session, principal: Principal, key: str) -> IdempotencyRecord | None:
    return db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.key == key,
        )
    )


def _existing(
    db: Session,
    principal: Principal,
    record: IdempotencyRecord,
    request_hash: str,
    operation: str,
    payment_type: PaymentType,
) -> PaymentMutationResult:
    if record.operation != operation or record.request_hash != request_hash:
        raise PaymentDomainError("idempotency key was reused with a different request")
    if record.resource_id is None:
        raise PaymentDomainError("idempotency record has no payment resource")
    return PaymentMutationResult(
        _get_payment(db, record.resource_id, principal, payment_type), replayed=True
    )


def _audit(
    db: Session,
    principal: Principal,
    payment: PaymentRecord,
    action: str,
    payload: dict[str, object],
) -> AuditEvent:
    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action=action,
        entity_type="payment",
        entity_id=payment.id,
        correlation_id=str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _store(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash: str,
    payment: PaymentRecord,
    response_status: int,
) -> None:
    db.add(
        IdempotencyRecord(
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=key,
            operation=operation,
            request_hash=request_hash,
            response_status=response_status,
            response_body={"payment_id": str(payment.id)},
            resource_id=payment.id,
        )
    )
    db.flush()


def _document(
    db: Session, principal: Principal, document_id: UUID, payment_type: PaymentType
) -> FinancialDocument:
    expected_type = "sales_invoice" if payment_type == "receipt" else "vendor_bill"
    document = db.scalar(
        select(FinancialDocument).where(
            FinancialDocument.id == document_id,
            FinancialDocument.tenant_id == principal.tenant_id,
            FinancialDocument.organization_id == principal.organization_id,
            FinancialDocument.document_type == expected_type,
        )
    )
    if document is None:
        raise PaymentDomainError("allocated document not found")
    if document.status != "posted":
        raise PaymentDomainError("only posted documents can be allocated")
    return document


def _posted_allocated(db: Session, principal: Principal, document_id: UUID) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), Decimal("0.00")))
        .join(PaymentRecord, PaymentRecord.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.document_id == document_id,
            PaymentAllocation.tenant_id == principal.tenant_id,
            PaymentAllocation.organization_id == principal.organization_id,
            PaymentRecord.status == "posted",
        )
    )
    return (value or Decimal("0.00")).quantize(MONEY)


def _validate_allocations(
    db: Session,
    principal: Principal,
    payload: PaymentCreate,
    payment_type: PaymentType,
) -> Decimal:
    allocation_total = Decimal("0.00")
    seen: set[UUID] = set()
    for allocation in payload.allocations:
        if allocation.document_id in seen:
            raise PaymentDomainError("a payment cannot allocate the same document twice")
        seen.add(allocation.document_id)
        document = _document(db, principal, allocation.document_id, payment_type)
        if document.partner_id != payload.partner_id:
            raise PaymentDomainError("allocated documents must belong to the payment partner")
        if document.currency_code != payload.currency_code.upper():
            raise PaymentDomainError("allocated documents must use the payment currency")
        outstanding = document.total - _posted_allocated(db, principal, document.id)
        if allocation.amount > outstanding:
            raise PaymentDomainError(
                f"allocation exceeds outstanding document balance ({document.document_number})"
            )
        allocation_total += allocation.amount
    allocation_total = allocation_total.quantize(MONEY)
    if allocation_total > payload.amount:
        raise PaymentDomainError("allocations cannot exceed payment amount")
    if allocation_total < payload.amount and not payload.unapplied_account_code:
        raise PaymentDomainError("an unapplied account is required for an unallocated amount")
    return allocation_total


def create_payment(
    db: Session,
    payload: PaymentCreate,
    principal: Principal,
    payment_type: PaymentType,
    idempotency_key: str,
) -> PaymentMutationResult:
    organization_id = _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash({"payment_type": payment_type, "payload": payload.model_dump(mode="json")})
    existing_record = _record(db, principal, key)
    if existing_record is not None:
        return _existing(
            db, principal, existing_record, request_hash, "payment.create", payment_type
        )
    allocation_total = _validate_allocations(db, principal, payload, payment_type)
    payment_number = payload.payment_number.strip().upper()
    if db.scalar(
        select(PaymentRecord.id).where(
            PaymentRecord.organization_id == organization_id,
            PaymentRecord.payment_type == payment_type,
            PaymentRecord.payment_number == payment_number,
        )
    ):
        raise PaymentDomainError("payment number already exists for this payment type")
    payment = PaymentRecord(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        payment_type=payment_type,
        payment_number=payment_number,
        partner_id=payload.partner_id,
        payment_date=payload.payment_date,
        currency_code=payload.currency_code.upper(),
        amount=payload.amount,
        cash_account_code=payload.cash_account_code.strip().upper(),
        unapplied_account_code=(
            payload.unapplied_account_code.strip().upper()
            if payload.unapplied_account_code
            else None
        ),
        memo=payload.memo.strip() if payload.memo else None,
        status="draft",
        allocations=[
            PaymentAllocation(
                tenant_id=principal.tenant_id,
                organization_id=organization_id,
                document_id=allocation.document_id,
                amount=allocation.amount,
            )
            for allocation in payload.allocations
        ],
    )
    db.add(payment)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise PaymentDomainError("payment number already exists for this payment type") from error
    _audit(
        db,
        principal,
        payment,
        "payment.create",
        {
            "payment_type": payment.payment_type,
            "payment_number": payment.payment_number,
            "amount": str(payment.amount),
            "allocated": str(allocation_total),
        },
    )
    _store(db, principal, key, "payment.create", request_hash, payment, 201)
    return PaymentMutationResult(payment)


def list_payments(
    db: Session, principal: Principal, payment_type: PaymentType, status: str | None = None
) -> list[PaymentRecord]:
    _org(principal)
    statement = _payment_query(principal, payment_type)
    if status is not None:
        statement = statement.where(PaymentRecord.status == status)
    return list(
        db.scalars(
            statement.order_by(PaymentRecord.payment_date.desc(), PaymentRecord.payment_number)
        ).all()
    )


def _posting_command(payment: PaymentRecord) -> JournalPostCommand:
    allocation_total = sum(
        (allocation.amount for allocation in payment.allocations), Decimal("0.00")
    )
    residual = payment.amount - allocation_total
    lines: list[JournalLineInput] = []
    if payment.payment_type == "receipt":
        lines.append(JournalLineInput(account_code=payment.cash_account_code, debit=payment.amount))
        for allocation in payment.allocations:
            document = allocation.document
            lines.append(
                JournalLineInput(
                    account_code=document.control_account_code,
                    credit=allocation.amount,
                    memo=f"Allocation {document.document_number}",
                )
            )
        if residual > 0:
            lines.append(
                JournalLineInput(account_code=payment.unapplied_account_code or "", credit=residual)
            )
    else:
        for allocation in payment.allocations:
            document = allocation.document
            lines.append(
                JournalLineInput(
                    account_code=document.control_account_code,
                    debit=allocation.amount,
                    memo=f"Allocation {document.document_number}",
                )
            )
        if residual > 0:
            lines.append(
                JournalLineInput(account_code=payment.unapplied_account_code or "", debit=residual)
            )
        lines.append(
            JournalLineInput(account_code=payment.cash_account_code, credit=payment.amount)
        )
    prefix = "RCPT" if payment.payment_type == "receipt" else "PAY"
    return JournalPostCommand(
        reference=f"{prefix}/{payment.payment_number}",
        memo=payment.memo or payment.payment_number,
        journal_date=payment.payment_date,
        source_type=payment.payment_type,
        source_id=payment.id,
        lines=lines,
    )


def post_payment(
    db: Session,
    payment_id: UUID,
    principal: Principal,
    payment_type: PaymentType,
    idempotency_key: str,
) -> PaymentMutationResult:
    _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash({"payment_type": payment_type, "payment_id": str(payment_id)})
    existing_record = _record(db, principal, key)
    if existing_record is not None:
        return _existing(db, principal, existing_record, request_hash, "payment.post", payment_type)
    payment = _get_payment(db, payment_id, principal, payment_type)
    if payment.status != "draft":
        raise PaymentDomainError("only draft payments can be posted")
    command = _posting_command(payment)
    try:
        ledger_result = post_journal_entry(
            db,
            command,
            principal,
            f"payment-ledger:{payment.id}:{request_hash[:64]}",
        )
    except LedgerDomainError as error:
        raise PaymentDomainError(str(error)) from error
    payment.status = "posted"
    payment.ledger_entry_id = ledger_result.entry_id
    payment.posted_at = datetime.now(UTC)
    payment.version += 1
    db.flush()
    _audit(
        db,
        principal,
        payment,
        "payment.post",
        {
            "payment_type": payment.payment_type,
            "payment_number": payment.payment_number,
            "ledger_entry_id": str(ledger_result.entry_id),
        },
    )
    _store(db, principal, key, "payment.post", request_hash, payment, 200)
    return PaymentMutationResult(payment)


__all__ = [
    "PaymentDomainError",
    "PaymentMutationResult",
    "create_payment",
    "list_payments",
    "post_payment",
]
