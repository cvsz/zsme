from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal
from app.db.models import (
    BankAccount,
    ChartAccount,
    FinancialDocument,
    JournalEntryRecord,
    JournalLineRecord,
    Organization,
    PaymentAllocation,
    PaymentRecord,
)
from app.domains.reports.schemas import (
    AccountReportRow,
    AgedBucket,
    AgedDocumentRow,
    AgedReport,
    BalanceSheetReport,
    CashFlowReport,
    CashFlowRow,
    GeneralLedgerReport,
    GeneralLedgerRow,
    ProfitLossReport,
    TrialBalanceReport,
    TrialBalanceRow,
)

MONEY = Decimal("0.01")
MAX_REPORT_ROWS = 10_000


class ReportDomainError(Exception):
    """A safe, expected reporting-domain failure."""


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0.00")).quantize(MONEY)


def _bounded_rows(rows: list[tuple], report_name: str) -> list[tuple]:
    if len(rows) > MAX_REPORT_ROWS:
        raise ReportDomainError(
            f"{report_name} exceeds the maximum of {MAX_REPORT_ROWS} rows; narrow the date range"
        )
    return rows


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

    rows = _bounded_rows(
        list(
            db.execute(
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
                .limit(MAX_REPORT_ROWS + 1)
            ).all()
        ),
        "trial balance",
    )

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


def profit_loss(
    db: Session,
    principal: Principal,
    from_date: date,
    to_date: date,
) -> ProfitLossReport:
    trial = trial_balance(db, principal, from_date, to_date)
    rows: list[AccountReportRow] = []
    for row in trial.rows:
        if row.account_type == "revenue":
            rows.append(
                AccountReportRow(
                    account_code=row.account_code,
                    account_name=row.account_name,
                    amount=_money(row.credit - row.debit),
                )
            )
        elif row.account_type == "expense":
            rows.append(
                AccountReportRow(
                    account_code=row.account_code,
                    account_name=row.account_name,
                    amount=_money(row.debit - row.credit),
                )
            )
    # Keep category totals independent from presentation ordering and support
    # negative corrective balances without dropping them from the report.
    revenue = _money(
        sum(
            (row.credit - row.debit for row in trial.rows if row.account_type == "revenue"),
            Decimal("0.00"),
        )
    )
    expenses = _money(
        sum(
            (row.debit - row.credit for row in trial.rows if row.account_type == "expense"),
            Decimal("0.00"),
        )
    )
    return ProfitLossReport(
        from_date=from_date,
        to_date=to_date,
        rows=rows,
        total_revenue=revenue,
        total_expenses=expenses,
        net_income=_money(revenue - expenses),
    )


def balance_sheet(
    db: Session,
    principal: Principal,
    as_of: date,
) -> BalanceSheetReport:
    trial = trial_balance(db, principal, date(1900, 1, 1), as_of)

    def rows_for(account_type: str, *, credit_nature: bool = False) -> list[AccountReportRow]:
        return [
            AccountReportRow(
                account_code=row.account_code,
                account_name=row.account_name,
                amount=_money(
                    (row.credit - row.debit) if credit_nature else (row.debit - row.credit)
                ),
            )
            for row in trial.rows
            if row.account_type == account_type
        ]

    assets = rows_for("asset")
    liabilities = rows_for("liability", credit_nature=True)
    equity = rows_for("equity", credit_nature=True)
    profit = profit_loss(db, principal, date(1900, 1, 1), as_of)
    total_assets = _money(sum((row.amount for row in assets), Decimal("0.00")))
    total_liabilities = _money(sum((row.amount for row in liabilities), Decimal("0.00")))
    total_equity = _money(sum((row.amount for row in equity), Decimal("0.00")))
    return BalanceSheetReport(
        as_of=as_of,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        net_income=profit.net_income,
        total_liabilities_and_equity=_money(total_liabilities + total_equity + profit.net_income),
    )


def general_ledger(
    db: Session,
    principal: Principal,
    from_date: date,
    to_date: date,
) -> GeneralLedgerReport:
    if principal.organization_id is None:
        raise ReportDomainError("an organization is required for reporting")
    if from_date > to_date:
        raise ReportDomainError("from_date must be on or before to_date")
    values = _bounded_rows(
        list(
            db.execute(
                select(
                    JournalEntryRecord.id,
                    JournalEntryRecord.reference,
                    JournalEntryRecord.journal_date,
                    JournalEntryRecord.source_type,
                    JournalLineRecord.account_code,
                    JournalLineRecord.memo,
                    JournalLineRecord.debit,
                    JournalLineRecord.credit,
                )
                .join(JournalLineRecord, JournalLineRecord.entry_id == JournalEntryRecord.id)
                .where(
                    JournalEntryRecord.tenant_id == principal.tenant_id,
                    JournalEntryRecord.organization_id == principal.organization_id,
                    JournalEntryRecord.status == "posted",
                    JournalEntryRecord.journal_date >= from_date,
                    JournalEntryRecord.journal_date <= to_date,
                    JournalLineRecord.tenant_id == principal.tenant_id,
                    JournalLineRecord.organization_id == principal.organization_id,
                )
                .order_by(
                    JournalEntryRecord.journal_date,
                    JournalEntryRecord.created_at,
                    JournalEntryRecord.id,
                    JournalLineRecord.line_no,
                )
                .limit(MAX_REPORT_ROWS + 1)
            ).all()
        ),
        "general ledger",
    )
    rows = [
        GeneralLedgerRow(
            entry_id=entry_id,
            reference=reference,
            journal_date=journal_date,
            account_code=account_code,
            memo=memo,
            source_type=source_type,
            debit=_money(debit),
            credit=_money(credit),
        )
        for (
            entry_id,
            reference,
            journal_date,
            source_type,
            account_code,
            memo,
            debit,
            credit,
        ) in values
    ]
    return GeneralLedgerReport(
        from_date=from_date,
        to_date=to_date,
        rows=rows,
        total_debit=_money(sum((row.debit for row in rows), Decimal("0.00"))),
        total_credit=_money(sum((row.credit for row in rows), Decimal("0.00"))),
    )


def cash_flow(
    db: Session,
    principal: Principal,
    from_date: date,
    to_date: date,
) -> CashFlowReport:
    """Return direct cash-account movement from the posted ledger.

    Cash accounts are explicit bank-account mappings or chart accounts marked
    as cash equivalents, rather than inferred from account-code conventions.
    This keeps the report auditable while the
    chart of accounts does not yet model operating, investing, or financing
    classifications.
    """
    if principal.organization_id is None:
        raise ReportDomainError("an organization is required for reporting")
    if from_date > to_date:
        raise ReportDomainError("from_date must be on or before to_date")

    organization_currency = db.scalar(
        select(Organization.default_currency).where(
            Organization.id == principal.organization_id,
            Organization.tenant_id == principal.tenant_id,
        )
    )
    if organization_currency is None:
        raise ReportDomainError("organization not found")
    currency_code = organization_currency.upper()
    active_bank_accounts = list(
        db.execute(
            select(BankAccount.ledger_account_code, BankAccount.currency_code).where(
                BankAccount.tenant_id == principal.tenant_id,
                BankAccount.organization_id == principal.organization_id,
                BankAccount.is_active.is_(True),
            )
        ).all()
    )
    configured_currencies = {
        str(account_currency).upper() for _, account_currency in active_bank_accounts
    }
    if configured_currencies - {currency_code}:
        raise ReportDomainError(
            f"cash flow requires active bank accounts to use organization currency {currency_code}"
        )
    explicit_cash_codes = set(
        db.scalars(
            select(ChartAccount.code).where(
                ChartAccount.tenant_id == principal.tenant_id,
                ChartAccount.organization_id == principal.organization_id,
                ChartAccount.is_active.is_(True),
                ChartAccount.is_cash_equivalent.is_(True),
            )
        ).all()
    )
    configured_cash_codes = {
        str(account_code).strip().upper() for account_code, _ in active_bank_accounts
    } | {str(account_code).strip().upper() for account_code in explicit_cash_codes}
    period = and_(
        JournalEntryRecord.journal_date >= from_date,
        JournalEntryRecord.journal_date <= to_date,
    )
    opening = JournalEntryRecord.journal_date < from_date
    values = _bounded_rows(
        list(
            db.execute(
                select(
                    JournalLineRecord.account_code,
                    ChartAccount.name,
                    func.coalesce(
                        func.sum(case((opening, JournalLineRecord.debit), else_=Decimal("0.00"))),
                        Decimal("0.00"),
                    ).label("opening_debit"),
                    func.coalesce(
                        func.sum(case((opening, JournalLineRecord.credit), else_=Decimal("0.00"))),
                        Decimal("0.00"),
                    ).label("opening_credit"),
                    func.coalesce(
                        func.sum(case((period, JournalLineRecord.debit), else_=Decimal("0.00"))),
                        Decimal("0.00"),
                    ).label("period_debit"),
                    func.coalesce(
                        func.sum(case((period, JournalLineRecord.credit), else_=Decimal("0.00"))),
                        Decimal("0.00"),
                    ).label("period_credit"),
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
                    JournalLineRecord.account_code.in_(configured_cash_codes),
                )
                .group_by(JournalLineRecord.account_code, ChartAccount.name)
                .order_by(JournalLineRecord.account_code)
                .limit(MAX_REPORT_ROWS + 1)
            ).all()
        ),
        "cash flow",
    )

    rows: list[CashFlowRow] = []
    for (
        account_code,
        account_name,
        opening_debit,
        opening_credit,
        period_debit,
        period_credit,
    ) in values:
        opening_balance = _money(opening_debit - opening_credit)
        inflow = _money(period_debit)
        outflow = _money(period_credit)
        net_change = _money(inflow - outflow)
        rows.append(
            CashFlowRow(
                account_code=account_code,
                account_name=account_name,
                opening_balance=opening_balance,
                inflow=inflow,
                outflow=outflow,
                net_change=net_change,
                closing_balance=_money(opening_balance + net_change),
            )
        )

    opening_cash = _money(sum((row.opening_balance for row in rows), Decimal("0.00")))
    total_inflow = _money(sum((row.inflow for row in rows), Decimal("0.00")))
    total_outflow = _money(sum((row.outflow for row in rows), Decimal("0.00")))
    net_change = _money(total_inflow - total_outflow)
    return CashFlowReport(
        from_date=from_date,
        to_date=to_date,
        method="direct_cash_account_movement",
        currency_code=currency_code,
        configuration_status=("ready" if configured_cash_codes else "configuration_required"),
        mapped_account_count=len(configured_cash_codes),
        rows=rows,
        opening_cash=opening_cash,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        net_change=net_change,
        closing_cash=_money(opening_cash + net_change),
    )


def aged_report(
    db: Session,
    principal: Principal,
    as_of: date,
    document_type: Literal["sales_invoice", "vendor_bill"],
) -> AgedReport:
    if principal.organization_id is None:
        raise ReportDomainError("an organization is required for reporting")
    payment_type = "receipt" if document_type == "sales_invoice" else "disbursement"
    allocations = (
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
            PaymentRecord.payment_date <= as_of,
        )
        .group_by(PaymentAllocation.document_id)
        .subquery()
    )
    values = _bounded_rows(
        list(
            db.execute(
                select(
                    FinancialDocument.id,
                    FinancialDocument.document_number,
                    FinancialDocument.partner_id,
                    FinancialDocument.issue_date,
                    FinancialDocument.due_date,
                    FinancialDocument.total,
                    func.coalesce(allocations.c.allocated_amount, Decimal("0.00")),
                )
                .outerjoin(allocations, allocations.c.document_id == FinancialDocument.id)
                .where(
                    FinancialDocument.tenant_id == principal.tenant_id,
                    FinancialDocument.organization_id == principal.organization_id,
                    FinancialDocument.document_type == document_type,
                    FinancialDocument.status == "posted",
                    FinancialDocument.issue_date <= as_of,
                )
                .order_by(FinancialDocument.due_date, FinancialDocument.document_number)
                .limit(MAX_REPORT_ROWS + 1)
            ).all()
        ),
        "aged report",
    )

    def bucket(due_date: date) -> AgedBucket:
        days_overdue = (as_of - due_date).days
        if days_overdue <= 0:
            return "current"
        if days_overdue <= 30:
            return "1_30"
        if days_overdue <= 60:
            return "31_60"
        if days_overdue <= 90:
            return "61_90"
        return "over_90"

    rows: list[AgedDocumentRow] = []
    bucket_totals: dict[AgedBucket, Decimal] = {
        "current": Decimal("0.00"),
        "1_30": Decimal("0.00"),
        "31_60": Decimal("0.00"),
        "61_90": Decimal("0.00"),
        "over_90": Decimal("0.00"),
    }
    for document_id, document_number, partner_id, issue_date, due_date, total, allocated in values:
        outstanding = max(_money(total - allocated), Decimal("0.00"))
        if outstanding == Decimal("0.00"):
            continue
        aged_bucket = bucket(due_date)
        bucket_totals[aged_bucket] += outstanding
        rows.append(
            AgedDocumentRow(
                document_id=document_id,
                document_number=document_number,
                partner_id=partner_id,
                issue_date=issue_date,
                due_date=due_date,
                total=_money(total),
                allocated=_money(allocated),
                outstanding=outstanding,
                bucket=aged_bucket,
            )
        )
    normalized_bucket_totals = {key: _money(value) for key, value in bucket_totals.items()}
    return AgedReport(
        as_of=as_of,
        document_type=document_type,
        rows=rows,
        bucket_totals=normalized_bucket_totals,
        current_total=normalized_bucket_totals["current"],
        overdue_total=_money(
            sum(
                (value for key, value in normalized_bucket_totals.items() if key != "current"),
                Decimal("0.00"),
            )
        ),
        total_outstanding=_money(sum((row.outstanding for row in rows), Decimal("0.00"))),
    )


__all__ = [
    "ReportDomainError",
    "aged_report",
    "balance_sheet",
    "cash_flow",
    "general_ledger",
    "profit_loss",
    "trial_balance",
]
