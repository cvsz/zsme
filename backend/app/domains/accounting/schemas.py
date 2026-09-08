from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]
PeriodStatus = Literal["open", "locked"]


class ChartAccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._/-]+$")
    name: str = Field(min_length=1, max_length=200)
    account_type: AccountType
    parent_id: UUID | None = None
    is_control: bool = False


class ChartAccountUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    is_control: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> ChartAccountUpdate:
        if not any(
            value is not None
            for field, value in self.model_dump().items()
            if field != "expected_version"
        ):
            raise ValueError("at least one account field must change")
        return self


class ChartAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    code: str
    name: str
    account_type: AccountType
    parent_id: UUID | None
    is_control: bool
    is_active: bool
    version: int


class FiscalPeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> FiscalPeriodCreate:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class FiscalPeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    name: str
    start_date: date
    end_date: date
    status: PeriodStatus
    locked_at: datetime | None
    version: int


__all__ = [
    "AccountType",
    "ChartAccountCreate",
    "ChartAccountRead",
    "ChartAccountUpdate",
    "FiscalPeriodCreate",
    "FiscalPeriodRead",
    "PeriodStatus",
]
