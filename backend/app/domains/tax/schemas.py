from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaxType = Literal["vat", "withholding"]


class TaxRateCreate(BaseModel):
    tax_type: TaxType
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._/-]+$")
    name: str = Field(min_length=1, max_length=200)
    rate: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> TaxRateCreate:
        if self.effective_to is not None and self.effective_from > self.effective_to:
            raise ValueError("effective_from must be on or before effective_to")
        return self


class TaxRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    tax_type: TaxType
    code: str
    name: str
    rate: Decimal
    effective_from: date
    effective_to: date | None
    is_active: bool
    version: int


__all__ = ["TaxRateCreate", "TaxRateRead", "TaxType"]
