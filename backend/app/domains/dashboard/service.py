from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import (
    AuditEvent,
    BankAccount,
    BankTransaction,
    BusinessPartner,
    FinancialDocument,
    JournalEntryRecord,
    JournalLineRecord,
    Organization,
    PaymentAllocation,
    PaymentRecord,
)
from app.domains.dashboard.schemas import DashboardActivity, DashboardSummary

MONEY = Decimal("0.01")


class DashboardDomainError(Exception):
    """A safe, expected dashboard aggregation failure."""


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0.00")).quantize(MONEY)


def _organization_id(principal: Principal):
    if principal.organization_id is None:
        raise DashboardDomainError("an organization is required for dashboard operations")
    return principal.organization_id


def _posted_allocations(
    db: Session,
    principal: Principal,
    payment_type: str,
):
    return (
        select(
            PaymentAllocation.document_id.label("document_id"),
            func.sum(PaymentAllocation.amount).label("allocated_amount"),
        )
        .join(PaymentRecord, PaymentRecord.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.tenant_id == principal.tenant_id,
            PaymentAllocation.organization_id == principal.organization_id,
            PaymentRecord.tenant_id == principal.tenant_id,
            PaymentRecord.organization_id == principal.organization_id,
            PaymentRecord.payment_type == payment_type,
            PaymentRecord.status == "posted",
        )
        .group_by(PaymentAllocation.document_id)
        .subquery()
    )


def _document_position(
    db: Session,
    principal: Principal,
    as_of: date,
    document_type: str,
    payment_type: str,
) -> tuple[Decimal, int]:
    allocations = _posted_allocations(db, principal, payment_type)
    scope = [
        FinancialDocument.tenant_id == principal.tenant_id,
        FinancialDocument.organization_id == principal.organization_id,
        FinancialDocument.document_type == document_type,
        FinancialDocument.status == "posted",
        FinancialDocument.issue_date <= as_of,
    ]
    outstanding = db.scalar(
        select(
            func.coalesce(
                func.sum(
                    FinancialDocument.total
                    - func.coalesce(allocations.c.allocated_amount, Decimal("0.00"))
                ),
                Decimal("0.00"),
            )
        )
        .select_from(FinancialDocument)
        .outerjoin(allocations, allocations.c.document_id == FinancialDocument.id)
        .where(*scope)
    )
    open_count = db.scalar(
        select(func.count(FinancialDocument.id))
        .select_from(FinancialDocument)
        .outerjoin(allocations, allocations.c.document_id == FinancialDocument.id)
        .where(
            *scope,
            FinancialDocument.total
            > func.coalesce(allocations.c.allocated_amount, Decimal("0.00")),
        )
    ) or 0
    return max(_money(outstanding), Decimal("0.00")), int(open_count)


def dashboard_summary(
    db: Session,
    principal: Principal,
    as_of: date | None = None,
) -> DashboardSummary:
    organization_id = _organization_id(principal)
    report_date = as_of or date.today()
    organization = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == principal.tenant_id,
        )
    )
    if organization is None:
        raise DashboardDomainError("organization not found")

    bank_codes = list(
        db.scalars(
            select(BankAccount.ledger_account_code).where(
                BankAccount.tenant_id == principal.tenant_id,
                BankAccount.organization_id == organization_id,
                BankAccount.is_active.is_(True),
            )
        ).all()
    )
    cash_position: Decimal | None = None
    if bank_codes:
        cash_position = db.scalar(
            select(
                func.sum(JournalLineRecord.debit - JournalLineRecord.credit),
            )
            .select_from(JournalLineRecord)
            .join(
                JournalEntryRecord,
                and_(
                    JournalEntryRecord.id == JournalLineRecord.entry_id,
                    JournalEntryRecord.tenant_id == principal.tenant_id,
                    JournalEntryRecord.organization_id == organization_id,
                ),
            )
            .where(
                JournalLineRecord.tenant_id == principal.tenant_id,
                JournalLineRecord.organization_id == organization_id,
                JournalLineRecord.account_code.in_(bank_codes),
                JournalEntryRecord.status == "posted",
                JournalEntryRecord.journal_date <= report_date,
            )
        )
        cash_position = _money(cash_position)

    receivables, open_invoices = _document_position(
        db, principal, report_date, "sales_invoice", "receipt"
    )
    payables, open_bills = _document_position(
        db, principal, report_date, "vendor_bill", "disbursement"
    )

    customer_count = db.scalar(
        select(func.count(BusinessPartner.id)).where(
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == organization_id,
            BusinessPartner.is_active.is_(True),
            BusinessPartner.partner_type.in_(("customer", "both")),
        )
    ) or 0
    vendor_count = db.scalar(
        select(func.count(BusinessPartner.id)).where(
            BusinessPartner.tenant_id == principal.tenant_id,
            BusinessPartner.organization_id == organization_id,
            BusinessPartner.is_active.is_(True),
            BusinessPartner.partner_type.in_(("vendor", "both")),
        )
    ) or 0
    unmatched_bank_transactions = db.scalar(
        select(func.count(BankTransaction.id)).where(
            BankTransaction.tenant_id == principal.tenant_id,
            BankTransaction.organization_id == organization_id,
            BankTransaction.status == "unmatched",
            BankTransaction.transaction_date <= report_date,
        )
    ) or 0
    recent_activity = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == principal.tenant_id,
                AuditEvent.organization_id == organization_id,
            )
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(8)
        ).all()
    )

    return DashboardSummary(
        organization_id=organization_id,
        as_of=report_date,
        currency_code=organization.default_currency,
        cash_position=cash_position,
        receivables=receivables,
        payables=payables,
        open_invoices=open_invoices,
        open_bills=open_bills,
        customer_count=int(customer_count),
        vendor_count=int(vendor_count),
        unmatched_bank_transactions=int(unmatched_bank_transactions),
        recent_activity=[
            DashboardActivity(
                id=event.id,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                correlation_id=event.correlation_id,
                created_at=event.created_at,
            )
            for event in recent_activity
        ],
    )


__all__ = ["DashboardDomainError", "dashboard_summary"]
