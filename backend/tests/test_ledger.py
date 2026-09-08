from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.ledger import JournalEntry, JournalLine


def test_balanced_entry() -> None:
    entry = JournalEntry(
        reference="INV/2026/00001",
        lines=[
            JournalLine(account_code="1100", debit="1070.00"),
            JournalLine(account_code="4000", credit="1000.00"),
            JournalLine(account_code="2101", credit="70.00"),
        ],
    )

    assert entry.total_debit == Decimal("1070.00")
    assert entry.total_credit == Decimal("1070.00")


def test_unbalanced_entry_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unbalanced journal entry"):
        JournalEntry(
            reference="BAD/1",
            lines=[
                JournalLine(account_code="1100", debit="100.00"),
                JournalLine(account_code="4000", credit="99.00"),
            ],
        )


def test_line_cannot_debit_and_credit() -> None:
    with pytest.raises(ValidationError, match="both debit and credit"):
        JournalLine(account_code="1100", debit="100.00", credit="100.00")


def test_zero_value_line_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must contain a debit or credit"):
        JournalLine(account_code="1100")
