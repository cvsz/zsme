from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

ZERO = Decimal("0")


class JournalLine(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    debit: Decimal = Field(default=ZERO, ge=ZERO, max_digits=18, decimal_places=2)
    credit: Decimal = Field(default=ZERO, ge=ZERO, max_digits=18, decimal_places=2)
    memo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_one_side(self) -> "JournalLine":
        if self.debit > ZERO and self.credit > ZERO:
            raise ValueError("a journal line cannot contain both debit and credit")
        if self.debit == ZERO and self.credit == ZERO:
            raise ValueError("a journal line must contain a debit or credit amount")
        return self


class JournalEntry(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=500)
    lines: list[JournalLine] = Field(min_length=2)

    @property
    def total_debit(self) -> Decimal:
        return sum((line.debit for line in self.lines), ZERO)

    @property
    def total_credit(self) -> Decimal:
        return sum((line.credit for line in self.lines), ZERO)

    def assert_balanced(self) -> None:
        if self.total_debit != self.total_credit:
            raise ValueError(
                f"unbalanced journal entry: debit={self.total_debit} credit={self.total_credit}"
            )

    @model_validator(mode="after")
    def validate_balanced(self) -> "JournalEntry":
        self.assert_balanced()
        return self
