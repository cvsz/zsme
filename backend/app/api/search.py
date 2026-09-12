from __future__ import annotations

from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.api.dependencies import PrincipalDep, SessionDep
from app.db.models import (
    BankTransaction,
    BusinessPartner,
    FinancialDocument,
    JournalEntryRecord,
    PaymentRecord,
)

router = APIRouter(prefix="/v1/search", tags=["search"])

SearchKind = Literal[
    "partner",
    "invoice",
    "bill",
    "receipt",
    "disbursement",
    "journal",
    "bank_transaction",
]


class SearchResult(BaseModel):
    kind: SearchKind
    id: UUID
    label: str
    meta: str
    href: str


class SearchResponse(BaseModel):
    items: list[SearchResult]


def _allowed(principal, permission: str) -> bool:
    return permission in principal.permissions or "*" in principal.permissions


@router.get("", response_model=SearchResponse)
def search_workspace(
    principal: PrincipalDep,
    db: SessionDep,
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> SearchResponse:
    if principal.organization_id is None:
        return SearchResponse(items=[])

    term = q.strip()
    if len(term) < 2:
        return SearchResponse(items=[])

    like = f"%{term}%"
    remaining = limit
    items: list[SearchResult] = []

    if remaining and _allowed(principal, "partner:read"):
        rows = db.execute(
            select(
                BusinessPartner.id,
                BusinessPartner.partner_code,
                BusinessPartner.display_name,
                BusinessPartner.partner_type,
            )
            .where(
                BusinessPartner.tenant_id == principal.tenant_id,
                BusinessPartner.organization_id == principal.organization_id,
                or_(
                    BusinessPartner.partner_code.ilike(like),
                    BusinessPartner.display_name.ilike(like),
                    BusinessPartner.legal_name.ilike(like),
                ),
            )
            .order_by(BusinessPartner.partner_code)
            .limit(remaining)
        ).all()
        items.extend(
            SearchResult(
                kind="partner",
                id=partner_id,
                label=f"{partner_code} · {display_name}",
                meta=partner_type,
                href=f"/partners?search={quote(partner_code)}",
            )
            for partner_id, partner_code, display_name, partner_type in rows
        )
        remaining = limit - len(items)

    for document_type, permission, kind, href in (
        ("sales_invoice", "ar:read", "invoice", "/invoices"),
        ("vendor_bill", "ap:read", "bill", "/bills"),
    ):
        if not remaining or not _allowed(principal, permission):
            continue
        rows = db.execute(
            select(
                FinancialDocument.id,
                FinancialDocument.document_number,
                FinancialDocument.status,
                FinancialDocument.total,
                FinancialDocument.currency_code,
            )
            .where(
                FinancialDocument.tenant_id == principal.tenant_id,
                FinancialDocument.organization_id == principal.organization_id,
                FinancialDocument.document_type == document_type,
                or_(
                    FinancialDocument.document_number.ilike(like),
                    FinancialDocument.memo.ilike(like),
                ),
            )
            .order_by(FinancialDocument.issue_date.desc())
            .limit(remaining)
        ).all()
        items.extend(
            SearchResult(
                kind=kind,
                id=document_id,
                label=document_number,
                meta=f"{status} · {currency_code} {total}",
                href=f"{href}?search={quote(document_number)}",
            )
            for document_id, document_number, status, total, currency_code in rows
        )
        remaining = limit - len(items)

    for payment_type, permission, kind, href in (
        ("receipt", "ar:read", "receipt", "/receipts"),
        ("disbursement", "ap:read", "disbursement", "/disbursements"),
    ):
        if not remaining or not _allowed(principal, permission):
            continue
        rows = db.execute(
            select(
                PaymentRecord.id,
                PaymentRecord.payment_number,
                PaymentRecord.status,
                PaymentRecord.amount,
                PaymentRecord.currency_code,
            )
            .where(
                PaymentRecord.tenant_id == principal.tenant_id,
                PaymentRecord.organization_id == principal.organization_id,
                PaymentRecord.payment_type == payment_type,
                or_(
                    PaymentRecord.payment_number.ilike(like),
                    PaymentRecord.memo.ilike(like),
                ),
            )
            .order_by(PaymentRecord.payment_date.desc())
            .limit(remaining)
        ).all()
        items.extend(
            SearchResult(
                kind=kind,
                id=payment_id,
                label=payment_number,
                meta=f"{status} · {currency_code} {amount}",
                href=href,
            )
            for payment_id, payment_number, status, amount, currency_code in rows
        )
        remaining = limit - len(items)

    if remaining and _allowed(principal, "accounting:read"):
        rows = db.execute(
            select(
                JournalEntryRecord.id,
                JournalEntryRecord.reference,
                JournalEntryRecord.journal_date,
                JournalEntryRecord.source_type,
            )
            .where(
                JournalEntryRecord.tenant_id == principal.tenant_id,
                JournalEntryRecord.organization_id == principal.organization_id,
                JournalEntryRecord.status == "posted",
                or_(
                    JournalEntryRecord.reference.ilike(like),
                    JournalEntryRecord.memo.ilike(like),
                ),
            )
            .order_by(JournalEntryRecord.journal_date.desc())
            .limit(remaining)
        ).all()
        items.extend(
            SearchResult(
                kind="journal",
                id=entry_id,
                label=reference,
                meta=f"{journal_date.isoformat()} · {source_type or 'journal'}",
                href=f"/accounting?reference={quote(reference)}",
            )
            for entry_id, reference, journal_date, source_type in rows
        )
        remaining = limit - len(items)

    if remaining and _allowed(principal, "banking:read"):
        rows = db.execute(
            select(
                BankTransaction.id,
                BankTransaction.external_id,
                BankTransaction.description,
                BankTransaction.amount,
                BankTransaction.status,
            )
            .where(
                BankTransaction.tenant_id == principal.tenant_id,
                BankTransaction.organization_id == principal.organization_id,
                or_(
                    BankTransaction.external_id.ilike(like),
                    BankTransaction.description.ilike(like),
                    BankTransaction.reference.ilike(like),
                ),
            )
            .order_by(BankTransaction.transaction_date.desc())
            .limit(remaining)
        ).all()
        items.extend(
            SearchResult(
                kind="bank_transaction",
                id=transaction_id,
                label=external_id,
                meta=f"{status} · {amount} · {description}",
                href="/banking",
            )
            for transaction_id, external_id, description, amount, status in rows
        )

    return SearchResponse(items=items[:limit])


__all__ = ["router"]
