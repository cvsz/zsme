from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import ChartAccount, JournalEntryRecord, JournalLineRecord
from app.domains.reports.schemas import TrialBalanceReport, TrialBalanceRow

MONEY = Decimal("0.01")


class ReportDomainError(Exception):
    """A safe, expected reporting-domain failure."""


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0.00")).quantize(MONEY)


def trial_balance(
    db: Session,
    principal: Principal,
    from_date: date,
    to_date: date,
) -> TrialBalanceReport:
    if principal.organization_id is None:
        raise ReportDomainError("an organization is required for reporting")
    if from_date > to_date:
        raise ReportDomainError("from_date must be on or before to_date")

    rows = db.execute(
        select(
            JournalLineRecord.account_code,
            ChartAccount.name,
            ChartAccount.account_type,
            func.coalesce(func.sum(JournalLineRecord.debit), Decimal("0.00")),
            func.coalesce(func.sum(JournalLineRecord.credit), Decimal("0.00")),
        )
        .join(
            JournalEntryRecord,
            and_(
                JournalEntryRecord.id == JournalLineRecord.entry_id,
                JournalEntryRecord.tenant_id == principal.tenant_id,
                JournalEntryRecord.organization_id == principal.organization_id,
            ),
        )
        .outerjoin(
            ChartAccount,
            and_(
                ChartAccount.id == JournalLineRecord.account_id,
                ChartAccount.tenant_id == principal.tenant_id,
                ChartAccount.organization_id == principal.organization_id,
            ),
        )
        .where(
            JournalLineRecord.tenant_id == principal.tenant_id,
            JournalLineRecord.organization_id == principal.organization_id,
            JournalEntryRecord.status == "posted",
            JournalEntryRecord.journal_date >= from_date,
            JournalEntryRecord.journal_date <= to_date,
        )
        .group_by(
            JournalLineRecord.account_code,
            ChartAccount.name,
            ChartAccount.account_type,
        )
        .order_by(JournalLineRecord.account_code)
    ).all()

    report_rows = [
        TrialBalanceRow(
            account_code=account_code,
            account_name=account_name,
            account_type=account_type,
            debit=_money(debit),
            credit=_money(credit),
            balance=_money(debit - credit),
        )
        for account_code, account_name, account_type, debit, credit in rows
    ]
    return TrialBalanceReport(
        from_date=from_date,
        to_date=to_date,
        rows=report_rows,
        total_debit=_money(sum((row.debit for row in report_rows), Decimal("0.00"))),
        total_credit=_money(sum((row.credit for row in report_rows), Decimal("0.00"))),
    )


__all__ = ["ReportDomainError", "trial_balance"]
