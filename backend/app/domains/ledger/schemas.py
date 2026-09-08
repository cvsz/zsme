from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.ledger import JournalEntry, JournalLine

ZERO = Decimal("0")


class JournalLineInput(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    debit: Decimal = Field(default=ZERO, ge=ZERO, max_digits=18, decimal_places=2)
    credit: Decimal = Field(default=ZERO, ge=ZERO, max_digits=18, decimal_places=2)
    memo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_one_side(self) -> "JournalLineInput":
        if self.debit > ZERO and self.credit > ZERO:
            raise ValueError("a journal line cannot contain both debit and credit")
        if self.debit == ZERO and self.credit == ZERO:
            raise ValueError("a journal line must contain a debit or credit amount")
        return self


class JournalPostCommand(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=500)
    journal_date: date
    source_type: str = Field(min_length=1, max_length=100)
    source_id: UUID | None = None
    reversal_of_id: UUID | None = None
    lines: list[JournalLineInput] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_balanced(self) -> "JournalPostCommand":
        JournalEntry(
            reference=self.reference,
            memo=self.memo,
            lines=[
                JournalLine(
                    account_code=line.account_code,
                    debit=line.debit,
                    credit=line.credit,
                    memo=line.memo,
                )
                for line in self.lines
            ],
        )
        return self


class JournalPostResult(BaseModel):
    entry_id: UUID
    status: Literal["posted", "already_posted"]
    total: Decimal
    audit_event_id: UUID


class JournalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    line_no: int
    account_code: str
    debit: Decimal
    credit: Decimal
    memo: str | None


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    organization_id: UUID
    fiscal_period_id: UUID | None
    reference: str
    journal_date: date
    memo: str | None
    status: Literal["posted"]
    source_type: str | None
    source_id: UUID | None
    reversal_of_id: UUID | None
    posted_at: datetime | None
    created_at: datetime
    lines: list[JournalLineRead]
    total_debit: Decimal
    total_credit: Decimal


class JournalEntryPage(BaseModel):
    items: list[JournalEntryRead] = Field(default_factory=list)
    limit: int
    offset: int
    total: int
    next_offset: int | None


__all__ = [
    "JournalEntryPage",
    "JournalEntryRead",
    "JournalLineInput",
    "JournalLineRead",
    "JournalPostCommand",
    "JournalPostResult",
]
