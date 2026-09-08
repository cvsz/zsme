from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.db.models import (
    AuditEvent,
    BusinessPartner,
    FinancialDocument,
    FinancialDocumentLine,
    IdempotencyRecord,
)
from app.domains.documents.schemas import DocumentCreate, DocumentType
from app.domains.ledger.schemas import JournalLineInput, JournalPostCommand
from app.domains.ledger.service import DomainError as LedgerDomainError
from app.domains.ledger.service import post_journal_entry

MONEY = Decimal("0.01")


class DocumentDomainError(Exception):
    """A safe, expected financial-document domain failure."""


@dataclass(frozen=True)
class DocumentMutationResult:
    document: FinancialDocument
    replayed: bool = False


def _request_hash(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _validate_key(idempotency_key: str) -> str:
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 200:
        raise DocumentDomainError("a valid idempotency key is required")
    return normalized_key


def _require_organization(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise DocumentDomainError("an organization is required for document operations")
    return principal.organization_id


def _document_query(principal: Principal, document_type: DocumentType):
    return (
        select(FinancialDocument)
        .options(selectinload(FinancialDocument.lines))
        .where(
            FinancialDocument.tenant_id == principal.tenant_id,
            FinancialDocument.organization_id == principal.organization_id,
            FinancialDocument.document_type == document_type,
        )
    )


def _get_scoped_document(
    db: Session, document_id: UUID, principal: Principal, document_type: DocumentType
) -> FinancialDocument:
    _require_organization(principal)
    document = db.scalar(
        _document_query(principal, document_type).where(FinancialDocument.id == document_id)
    )
    if document is None:
        raise DocumentDomainError("document not found")
    return document


def _existing_result(
    db: Session,
    principal: Principal,
    record: IdempotencyRecord,
    request_hash: str,
    operation: str,
    document_type: DocumentType,
) -> DocumentMutationResult:
    if record.operation != operation or record.request_hash != request_hash:
        raise DocumentDomainError("idempotency key was reused with a different request")
    if record.resource_id is None:
        raise DocumentDomainError("idempotency record has no document resource")
    document = _get_scoped_document(db, record.resource_id, principal, document_type)
    return DocumentMutationResult(document=document, replayed=True)


def _find_existing(
    db: Session,
    principal: Principal,
    key: str,
    request_hash: str,
    operation: str,
    document_type: DocumentType,
) -> DocumentMutationResult | None:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.key == key,
        )
    )
    if record is None:
        return None
    return _existing_result(db, principal, record, request_hash, operation, document_type)


def _audit(
    db: Session,
    principal: Principal,
    document: FinancialDocument,
    action: str,
    payload: dict[str, object],
) -> AuditEvent:
    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action=action,
        entity_type="financial_document",
        entity_id=document.id,
        correlation_id=str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _store_idempotency(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash: str,
    document: FinancialDocument,
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
            response_body={"document_id": str(document.id)},
            resource_id=document.id,
        )
    )
    db.flush()


def _partner_for_document(
    db: Session,
    principal: Principal,
    partner_id: UUID,
    document_type: DocumentType,
) -> BusinessPartner:
    partner = db.scalar(
        select(BusinessPartner).where(
            BusinessPartner.id == partner_id,
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == principal.organization_id,
        )
    )
    if partner is None:
        raise DocumentDomainError("partner not found")
    required_type = "customer" if document_type == "sales_invoice" else "vendor"
    if partner.partner_type not in (required_type, "both"):
        raise DocumentDomainError(
            f"{document_type} requires a partner with {required_type} capability"
        )
    if not partner.is_active:
        raise DocumentDomainError("partner is archived")
    return partner


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def create_document(
    db: Session,
    payload: DocumentCreate,
    principal: Principal,
    document_type: DocumentType,
    idempotency_key: str,
) -> DocumentMutationResult:
    organization_id = _require_organization(principal)
    key = _validate_key(idempotency_key)
    request_hash = _request_hash(
        {"document_type": document_type, "payload": payload.model_dump(mode="json")}
    )
    existing = _find_existing(db, principal, key, request_hash, "document.create", document_type)
    if existing is not None:
        return existing

    partner = _partner_for_document(db, principal, payload.partner_id, document_type)
    document_number = payload.document_number.strip().upper()
    duplicate = db.scalar(
        select(FinancialDocument.id).where(
            FinancialDocument.organization_id == organization_id,
            FinancialDocument.document_type == document_type,
            FinancialDocument.document_number == document_number,
        )
    )
    if duplicate is not None:
        raise DocumentDomainError("document number already exists for this document type")

    lines: list[FinancialDocumentLine] = []
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    for line_no, line_payload in enumerate(payload.lines, start=1):
        net_amount = _money(line_payload.quantity * line_payload.unit_price)
        tax_amount = _money(net_amount * line_payload.tax_rate / Decimal("100"))
        total_amount = net_amount + tax_amount
        subtotal += net_amount
        tax_total += tax_amount
        lines.append(
            FinancialDocumentLine(
                tenant_id=principal.tenant_id,
                organization_id=organization_id,
                line_no=line_no,
                description=line_payload.description.strip(),
                quantity=line_payload.quantity,
                unit_price=line_payload.unit_price,
                tax_rate=line_payload.tax_rate,
                net_amount=net_amount,
                tax_amount=tax_amount,
                total_amount=total_amount,
                account_code=line_payload.account_code.strip().upper(),
            )
        )

    document = FinancialDocument(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        document_type=document_type,
        document_number=document_number,
        partner_id=partner.id,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        currency_code=payload.currency_code.upper(),
        control_account_code=payload.control_account_code.strip().upper(),
        tax_account_code=(
            payload.tax_account_code.strip().upper() if payload.tax_account_code else None
        ),
        memo=payload.memo.strip() if payload.memo else None,
        subtotal=_money(subtotal),
        tax_total=_money(tax_total),
        total=_money(subtotal + tax_total),
        status="draft",
        lines=lines,
    )
    db.add(document)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise DocumentDomainError(
            "document number already exists for this document type"
        ) from error

    _audit(
        db,
        principal,
        document,
        "document.create",
        {
            "document_type": document.document_type,
            "document_number": document.document_number,
            "total": str(document.total),
        },
    )
    _store_idempotency(
        db, principal, key, "document.create", request_hash, document, response_status=201
    )
    return DocumentMutationResult(document=document)


def list_documents(
    db: Session,
    principal: Principal,
    document_type: DocumentType,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[FinancialDocument]:
    _require_organization(principal)
    statement = _document_query(principal, document_type)
    if status is not None:
        statement = statement.where(FinancialDocument.status == status)
    if search and search.strip():
        statement = statement.where(FinancialDocument.document_number.ilike(f"%{search.strip()}%"))
    statement = statement.order_by(
        FinancialDocument.issue_date.desc(), FinancialDocument.document_number
    )
    return list(db.scalars(statement).all())


def get_document(
    db: Session, document_id: UUID, principal: Principal, document_type: DocumentType
) -> FinancialDocument:
    return _get_scoped_document(db, document_id, principal, document_type)


def _posting_command(document: FinancialDocument) -> JournalPostCommand:
    line_inputs: list[JournalLineInput] = []
    if document.document_type == "sales_invoice":
        line_inputs.append(
            JournalLineInput(account_code=document.control_account_code, debit=document.total)
        )
        for line in document.lines:
            if line.net_amount > 0:
                line_inputs.append(
                    JournalLineInput(
                        account_code=line.account_code,
                        credit=line.net_amount,
                        memo=line.description,
                    )
                )
        if document.tax_total > 0:
            line_inputs.append(
                JournalLineInput(
                    account_code=document.tax_account_code or "", credit=document.tax_total
                )
            )
    else:
        for line in document.lines:
            if line.net_amount > 0:
                line_inputs.append(
                    JournalLineInput(
                        account_code=line.account_code,
                        debit=line.net_amount,
                        memo=line.description,
                    )
                )
        if document.tax_total > 0:
            line_inputs.append(
                JournalLineInput(
                    account_code=document.tax_account_code or "", debit=document.tax_total
                )
            )
        line_inputs.append(
            JournalLineInput(account_code=document.control_account_code, credit=document.total)
        )
    return JournalPostCommand(
        reference=f"{document.document_type.upper()}/{document.document_number}",
        memo=document.memo or document.document_number,
        journal_date=document.issue_date,
        source_type=document.document_type,
        source_id=document.id,
        lines=line_inputs,
    )


def post_document(
    db: Session,
    document_id: UUID,
    principal: Principal,
    document_type: DocumentType,
    idempotency_key: str,
) -> DocumentMutationResult:
    _require_organization(principal)
    key = _validate_key(idempotency_key)
    request_hash = _request_hash({"document_type": document_type, "document_id": str(document_id)})
    existing = _find_existing(db, principal, key, request_hash, "document.post", document_type)
    if existing is not None:
        return existing

    document = _get_scoped_document(db, document_id, principal, document_type)
    if document.status != "draft":
        raise DocumentDomainError("only draft documents can be posted")
    if not document.lines:
        raise DocumentDomainError("a document must contain at least one line")

    command = _posting_command(document)
    try:
        ledger_result = post_journal_entry(
            db,
            command,
            principal,
            f"document-ledger:{document.id}:{request_hash[:64]}",
        )
    except LedgerDomainError as error:
        raise DocumentDomainError(str(error)) from error

    document.status = "posted"
    document.ledger_entry_id = ledger_result.entry_id
    document.posted_at = datetime.now(UTC)
    document.version += 1
    db.flush()
    _audit(
        db,
        principal,
        document,
        "document.post",
        {
            "document_type": document.document_type,
            "document_number": document.document_number,
            "ledger_entry_id": str(ledger_result.entry_id),
            "ledger_audit_event_id": str(ledger_result.audit_event_id),
        },
    )
    _store_idempotency(
        db, principal, key, "document.post", request_hash, document, response_status=200
    )
    return DocumentMutationResult(document=document)


__all__ = [
    "DocumentDomainError",
    "DocumentMutationResult",
    "create_document",
    "get_document",
    "list_documents",
    "post_document",
]
