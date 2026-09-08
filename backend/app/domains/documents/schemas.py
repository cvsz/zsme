from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

DocumentType = Literal["sales_invoice", "vendor_bill"]
DocumentStatus = Literal["draft", "posted", "void"]


class DocumentLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    account_code: str = Field(min_length=1, max_length=32)


class DocumentCreate(BaseModel):
    document_number: str = Field(min_length=1, max_length=100)
    partner_id: UUID
    issue_date: date
    due_date: date
    currency_code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    control_account_code: str = Field(min_length=1, max_length=32)
    tax_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    memo: str | None = Field(default=None, max_length=500)
    lines: list[DocumentLineCreate] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates_and_tax_account(self) -> DocumentCreate:
        if self.issue_date > self.due_date:
            raise ValueError("due_date must be on or after issue_date")
        if any(line.tax_rate > 0 for line in self.lines) and not self.tax_account_code:
            raise ValueError("tax_account_code is required when a line has tax")
        return self


class DocumentLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    line_no: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    net_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    account_code: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    document_type: DocumentType
    document_number: str
    partner_id: UUID
    issue_date: date
    due_date: date
    currency_code: str
    control_account_code: str
    tax_account_code: str | None
    memo: str | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    status: DocumentStatus
    ledger_entry_id: UUID | None
    posted_at: datetime | None
    version: int
    lines: list[DocumentLineRead] = Field(default_factory=list)


__all__ = [
    "DocumentCreate",
    "DocumentLineCreate",
    "DocumentLineRead",
    "DocumentRead",
    "DocumentStatus",
    "DocumentType",
]
