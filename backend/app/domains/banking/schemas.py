from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BankImportStatus = Literal["staged", "committed", "failed"]
BankTransactionStatus = Literal["unmatched", "reconciled"]


class BankAccountCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    bank_name: str = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    ledger_account_code: str = Field(min_length=1, max_length=32)

    @field_validator("account_code", "name", "bank_name", "ledger_account_code", mode="before")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class BankAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    account_code: str
    name: str
    bank_name: str
    currency_code: str
    ledger_account_code: str
    is_active: bool
    version: int


class BankTransactionImport(BaseModel):
    external_id: str = Field(min_length=1, max_length=150)
    transaction_date: date
    value_date: date | None = None
    description: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=200)
    amount: Decimal = Field(max_digits=18, decimal_places=2)

    @field_validator("external_id", "description", mode="before")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("reference", mode="before")
    @classmethod
    def normalize_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_amount(self) -> BankTransactionImport:
        if self.amount == 0:
            raise ValueError("amount must not be zero")
        return self


class BankImportCreate(BaseModel):
    batch_reference: str = Field(min_length=1, max_length=150)
    source_name: str = Field(min_length=1, max_length=250)
    transactions: list[BankTransactionImport] = Field(min_length=1, max_length=10_000)

    @field_validator("batch_reference", "source_name", mode="before")
    @classmethod
    def normalize_batch_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class BankTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    bank_account_id: UUID
    import_batch_id: UUID
    external_id: str
    transaction_date: date
    value_date: date | None
    description: str
    reference: str | None
    amount: Decimal
    status: BankTransactionStatus
    matched_payment_id: UUID | None
    reconciled_at: datetime | None
    version: int


class BankImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    bank_account_id: UUID
    batch_reference: str
    source_name: str
    status: BankImportStatus
    transaction_count: int
    version: int
    transactions: list[BankTransactionRead] = Field(default_factory=list)


class BankReconcileRequest(BaseModel):
    payment_id: UUID


__all__ = [
    "BankAccountCreate",
    "BankAccountRead",
    "BankImportCreate",
    "BankImportRead",
    "BankImportStatus",
    "BankReconcileRequest",
    "BankTransactionImport",
    "BankTransactionRead",
    "BankTransactionStatus",
]
