from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
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
    FinancialDocumentLine,
    IdempotencyRecord,
    Organization,
    TaxRateRule,
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
    return request_hash(payload)


def _validate_key(idempotency_key: str) -> str:
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 200:
        raise DocumentDomainError("a valid idempotency key is required")
    return normalized_key


def _require_organization(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise DocumentDomainError("an organization is required for document operations")
    return principal.organization_id


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
        raise DocumentDomainError(str(error)) from error


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
    db: Session,
    document_id: UUID,
    principal: Principal,
    document_type: DocumentType,
    *,
    for_update: bool = False,
) -> FinancialDocument:
    _require_organization(principal)
    statement = _document_query(principal, document_type).where(FinancialDocument.id == document_id)
    if for_update:
        statement = statement.with_for_update()
    document = db.scalar(statement)
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
        correlation_id=principal.correlation_id or str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


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
    claim = _claim(db, principal, key, "document.create", request_hash)
    if claim.replayed:
        return _existing_result(
            db, principal, claim.record, request_hash, "document.create", document_type
        )

    partner = _partner_for_document(db, principal, payload.partner_id, document_type)
    organization = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == principal.tenant_id,
        )
    )
    if organization is None:
        raise DocumentDomainError("organization not found")
    if payload.currency_code.upper() != organization.default_currency.upper():
        raise DocumentDomainError(
            "foreign-currency documents are not supported until exchange-rate accounting is configured"
        )

    taxable_rates = {line.tax_rate for line in payload.lines if line.tax_rate > 0}
    if taxable_rates:
        if not organization.vat_registered:
            raise DocumentDomainError("organization is not VAT registered")
        configured_rates = set(
            db.scalars(
                select(TaxRateRule.rate).where(
                    TaxRateRule.tenant_id == principal.tenant_id,
                    TaxRateRule.organization_id == organization_id,
                    TaxRateRule.tax_type == "vat",
                    TaxRateRule.is_active.is_(True),
                    TaxRateRule.effective_from <= payload.issue_date,
                    (
                        TaxRateRule.effective_to.is_(None)
                        | (TaxRateRule.effective_to >= payload.issue_date)
                    ),
                )
            ).all()
        )
        allowed_rates = configured_rates or {organization.vat_rate}
        unsupported_rates = sorted(rate for rate in taxable_rates if rate not in allowed_rates)
        if unsupported_rates:
            rendered = ", ".join(str(rate) for rate in unsupported_rates)
            raise DocumentDomainError(
                f"VAT rate is not effective for the document date: {rendered}"
            )

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
    try:
        with db.begin_nested():
            db.add(document)
            db.flush()
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
            complete_idempotency(
                db,
                claim,
                resource_id=document.id,
                response_status=201,
                response_body={"document_id": str(document.id)},
            )
    except IntegrityError as error:
        db.delete(claim.record)
        db.flush()
        raise DocumentDomainError(
            "document number already exists for this document type"
        ) from error
    return DocumentMutationResult(document=document)


def list_documents(
    db: Session,
    principal: Principal,
    document_type: DocumentType,
    *,
    status: str | None = None,
    search: str | None = None,
    limit: int,
    offset: int,
) -> Page[FinancialDocument]:
    _require_organization(principal)
    statement = _document_query(principal, document_type)
    if status is not None:
        statement = statement.where(FinancialDocument.status == status)
    if search and search.strip():
        statement = statement.where(FinancialDocument.document_number.ilike(f"%{search.strip()}%"))
    statement = statement.order_by(
        FinancialDocument.issue_date.desc(), FinancialDocument.document_number
    )
    items = list(db.scalars(statement.offset(offset).limit(limit + 1)).all())
    return Page(items=items[:limit], has_more=len(items) > limit)


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
    claim = _claim(db, principal, key, "document.post", request_hash)
    if claim.replayed:
        return _existing_result(
            db, principal, claim.record, request_hash, "document.post", document_type
        )

    document = _get_scoped_document(db, document_id, principal, document_type, for_update=True)
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
    complete_idempotency(
        db,
        claim,
        resource_id=document.id,
        response_status=200,
        response_body={"document_id": str(document.id)},
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
