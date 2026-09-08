from __future__ import annotations

from datetime import date
from decimal import Decimal

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


__all__ = ["TrialBalanceReport", "TrialBalanceRow"]
