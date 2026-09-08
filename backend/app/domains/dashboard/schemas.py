from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DashboardActivity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None
    correlation_id: str
    created_at: datetime


class DashboardSummary(BaseModel):
    organization_id: UUID
    as_of: date
    currency_code: str
    cash_position: Decimal | None
    receivables: Decimal
    payables: Decimal
    open_invoices: int
    open_bills: int
    customer_count: int
    vendor_count: int
    unmatched_bank_transactions: int
    recent_activity: list[DashboardActivity]


__all__ = ["DashboardActivity", "DashboardSummary"]
