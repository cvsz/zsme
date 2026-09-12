from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.core.idempotency import (
    IdempotencyClaim,
    IdempotencyError,
    claim_idempotency,
    complete_idempotency,
    request_hash,
)
from app.core.pagination import Page
from app.db.models import (
    AuditEvent,
    BusinessPartner,
    FinancialDocument,
    PaymentAllocation,
    PaymentRecord,
)
from app.domains.currency import CurrencyPolicyError, enforce_base_currency
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
    return request_hash(payload)


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
    db: Session,
    payment_id: UUID,
    principal: Principal,
    payment_type: PaymentType,
    *,
    for_update: bool = False,
) -> PaymentRecord:
    _org(principal)
    statement = _payment_query(principal, payment_type).where(PaymentRecord.id == payment_id)
    if for_update:
        statement = statement.with_for_update()
    payment = db.scalar(statement)
    if payment is None:
        raise PaymentDomainError("payment not found")
    return payment


def _claim(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash_value: str,
) -> IdempotencyClaim:
    try:
        return claim_idempotency(
            db,
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=key,
            operation=operation,
            request_hash=request_hash_value,
        )
    except IdempotencyError as error:
        raise PaymentDomainError(str(error)) from error


def _existing(
    db: Session,
    principal: Principal,
    record,
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
        correlation_id=principal.correlation_id or str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _document(
    db: Session,
    principal: Principal,
    document_id: UUID,
    payment_type: PaymentType,
    *,
    for_update: bool = False,
) -> FinancialDocument:
    expected_type = "sales_invoice" if payment_type == "receipt" else "vendor_bill"
    statement = select(FinancialDocument).where(
        FinancialDocument.id == document_id,
        FinancialDocument.tenant_id == principal.tenant_id,
        FinancialDocument.organization_id == principal.organization_id,
        FinancialDocument.document_type == expected_type,
    )
    if for_update:
        statement = statement.with_for_update()
    document = db.scalar(statement)
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
        document = _document(db, principal, allocation.document_id, payment_type, for_update=True)
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


def _validate_persisted_allocations(
    db: Session, principal: Principal, payment: PaymentRecord
) -> None:
    """Recheck balances while holding document locks immediately before posting."""
    expected_partner_type = "customer" if payment.payment_type == "receipt" else "vendor"
    partner = db.scalar(
        select(BusinessPartner).where(
            BusinessPartner.id == payment.partner_id,
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == principal.organization_id,
        )
    )
    if partner is None:
        raise PaymentDomainError("payment partner not found")
    if partner.partner_type not in (expected_partner_type, "both"):
        raise PaymentDomainError(
            f"{payment.payment_type} requires a partner with {expected_partner_type} capability"
        )
    if not partner.is_active:
        raise PaymentDomainError("payment partner is archived")

    allocation_total = Decimal("0.00")
    seen: set[UUID] = set()
    for allocation in sorted(payment.allocations, key=lambda item: str(item.document_id)):
        if allocation.document_id in seen:
            raise PaymentDomainError("a payment cannot allocate the same document twice")
        seen.add(allocation.document_id)
        document = _document(
            db,
            principal,
            allocation.document_id,
            payment.payment_type,
            for_update=True,
        )
        if document.partner_id != payment.partner_id:
            raise PaymentDomainError("allocated documents must belong to the payment partner")
        if document.currency_code != payment.currency_code:
            raise PaymentDomainError("allocated documents must use the payment currency")
        outstanding = document.total - _posted_allocated(db, principal, document.id)
        if allocation.amount > outstanding:
            raise PaymentDomainError(
                f"allocation exceeds outstanding document balance ({document.document_number})"
            )
        allocation_total += allocation.amount

    allocation_total = allocation_total.quantize(MONEY)
    if allocation_total > payment.amount:
        raise PaymentDomainError("allocations cannot exceed payment amount")
    if allocation_total < payment.amount and not payment.unapplied_account_code:
        raise PaymentDomainError("an unapplied account is required for an unallocated amount")


def create_payment(
    db: Session,
    payload: PaymentCreate,
    principal: Principal,
    payment_type: PaymentType,
    idempotency_key: str,
) -> PaymentMutationResult:
    organization_id = _org(principal)
    try:
        currency_code = enforce_base_currency(db, principal, payload.currency_code)
    except CurrencyPolicyError as error:
        raise PaymentDomainError(str(error)) from error
    key = _key(idempotency_key)
    request_hash = _hash({"payment_type": payment_type, "payload": payload.model_dump(mode="json")})
    claim = _claim(db, principal, key, "payment.create", request_hash)
    if claim.replayed:
        return _existing(db, principal, claim.record, request_hash, "payment.create", payment_type)
    expected_partner_type = "customer" if payment_type == "receipt" else "vendor"
    partner = db.scalar(
        select(BusinessPartner).where(
            BusinessPartner.id == payload.partner_id,
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == organization_id,
        )
    )
    if partner is None:
        raise PaymentDomainError("payment partner not found")
    if partner.partner_type not in (expected_partner_type, "both"):
        raise PaymentDomainError(
            f"{payment_type} requires a partner with {expected_partner_type} capability"
        )
    if not partner.is_active:
        raise PaymentDomainError("payment partner is archived")
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
        currency_code=currency_code,
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
    try:
        with db.begin_nested():
            db.add(payment)
            db.flush()
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
            complete_idempotency(
                db,
                claim,
                resource_id=payment.id,
                response_status=201,
                response_body={"payment_id": str(payment.id)},
            )
    except IntegrityError as error:
        db.delete(claim.record)
        db.flush()
        raise PaymentDomainError("payment number already exists for this payment type") from error
    return PaymentMutationResult(payment)


def list_payments(
    db: Session,
    principal: Principal,
    payment_type: PaymentType,
    status: str | None = None,
    *,
    limit: int,
    offset: int,
) -> Page[PaymentRecord]:
    _org(principal)
    statement = _payment_query(principal, payment_type)
    if status is not None:
        statement = statement.where(PaymentRecord.status == status)
    items = list(
        db.scalars(
            statement.order_by(PaymentRecord.payment_date.desc(), PaymentRecord.payment_number)
            .offset(offset)
            .limit(limit + 1)
        ).all()
    )
    return Page(items=items[:limit], has_more=len(items) > limit)


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
    claim = _claim(db, principal, key, "payment.post", request_hash)
    if claim.replayed:
        return _existing(db, principal, claim.record, request_hash, "payment.post", payment_type)
    payment = _get_payment(db, payment_id, principal, payment_type, for_update=True)
    if payment.status != "draft":
        raise PaymentDomainError("only draft payments can be posted")
    try:
        enforce_base_currency(db, principal, payment.currency_code)
    except CurrencyPolicyError as error:
        raise PaymentDomainError(str(error)) from error
    _validate_persisted_allocations(db, principal, payment)
    command = _posting_command(payment)
    try:
        ledger_result = post_journal_entry(
            db,
            command,
            principal,
            f"payment-ledger:{payment.id}",
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
    complete_idempotency(
        db,
        claim,
        resource_id=payment.id,
        response_status=200,
        response_body={"payment_id": str(payment.id)},
    )
    return PaymentMutationResult(payment)


__all__ = [
    "PaymentDomainError",
    "PaymentMutationResult",
    "create_payment",
    "list_payments",
    "post_payment",
]
