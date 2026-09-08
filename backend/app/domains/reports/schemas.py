from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TrialBalanceRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_code: str
    account_name: str | None
    account_type: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


class TrialBalanceReport(BaseModel):
    from_date: date
    to_date: date
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal


class AccountReportRow(BaseModel):
    account_code: str
    account_name: str | None
    amount: Decimal


class ProfitLossReport(BaseModel):
    from_date: date
    to_date: date
    rows: list[AccountReportRow]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class BalanceSheetReport(BaseModel):
    as_of: date
    assets: list[AccountReportRow]
    liabilities: list[AccountReportRow]
    equity: list[AccountReportRow]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    net_income: Decimal
    total_liabilities_and_equity: Decimal


class GeneralLedgerRow(BaseModel):
    entry_id: UUID
    reference: str
    journal_date: date
    account_code: str
    memo: str | None
    source_type: str | None
    debit: Decimal
    credit: Decimal


class GeneralLedgerReport(BaseModel):
    from_date: date
    to_date: date
    rows: list[GeneralLedgerRow]
    total_debit: Decimal
    total_credit: Decimal


AgedBucket = Literal["current", "1_30", "31_60", "61_90", "over_90"]


class AgedDocumentRow(BaseModel):
    document_id: UUID
    document_number: str
    partner_id: UUID
    issue_date: date
    due_date: date
    total: Decimal
    allocated: Decimal
    outstanding: Decimal
    bucket: AgedBucket


class AgedReport(BaseModel):
    as_of: date
    document_type: Literal["sales_invoice", "vendor_bill"]
    rows: list[AgedDocumentRow]
    bucket_totals: dict[AgedBucket, Decimal]
    current_total: Decimal
    overdue_total: Decimal
    total_outstanding: Decimal


__all__ = [
    "AccountReportRow",
    "AgedBucket",
    "AgedDocumentRow",
    "AgedReport",
    "BalanceSheetReport",
    "GeneralLedgerReport",
    "GeneralLedgerRow",
    "ProfitLossReport",
    "TrialBalanceReport",
    "TrialBalanceRow",
]
