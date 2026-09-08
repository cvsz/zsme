from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PaymentType = Literal["receipt", "disbursement"]
PaymentStatus = Literal["draft", "posted", "void"]


class PaymentAllocationCreate(BaseModel):
    document_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class PaymentCreate(BaseModel):
    payment_number: str = Field(min_length=1, max_length=100)
    partner_id: UUID
    payment_date: date
    currency_code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    cash_account_code: str = Field(min_length=1, max_length=32)
    unapplied_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    memo: str | None = Field(default=None, max_length=500)
    allocations: list[PaymentAllocationCreate] = Field(default_factory=list, max_length=500)


class PaymentAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_id: UUID
    document_id: UUID
    amount: Decimal


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    payment_type: PaymentType
    payment_number: str
    partner_id: UUID
    payment_date: date
    currency_code: str
    amount: Decimal
    cash_account_code: str
    unapplied_account_code: str | None
    memo: str | None
    status: PaymentStatus
    ledger_entry_id: UUID | None
    posted_at: datetime | None
    version: int
    allocations: list[PaymentAllocationRead] = Field(default_factory=list)


__all__ = [
    "PaymentAllocationCreate",
    "PaymentAllocationRead",
    "PaymentCreate",
    "PaymentRead",
    "PaymentStatus",
    "PaymentType",
]
