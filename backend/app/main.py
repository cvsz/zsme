from fastapi import FastAPI

from app.domain.ledger import JournalEntry, JournalLine
from app.i18n import DEFAULT_LOCALE, FALLBACK_LOCALE, SUPPORTED_LOCALES

app = FastAPI(
    title="ZSME Accounting API",
    version="0.1.0",
    description="Thailand-first SME accounting API with double-entry accounting invariants.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "zsme-api"}


@app.get("/v1/i18n/locales")
def locales() -> dict[str, object]:
    return {
        "default": DEFAULT_LOCALE,
        "fallback": FALLBACK_LOCALE,
        "supported": list(SUPPORTED_LOCALES),
    }


@app.post("/v1/accounting/validate-entry")
def validate_entry(entry: JournalEntry) -> dict[str, object]:
    entry.assert_balanced()
    return {
        "balanced": True,
        "debit": str(entry.total_debit),
        "credit": str(entry.total_credit),
        "lines": len(entry.lines),
    }


@app.get("/v1/accounting/example-entry", response_model=JournalEntry)
def example_entry() -> JournalEntry:
    return JournalEntry(
        reference="INV/2026/00001",
        memo="Example customer invoice",
        lines=[
            JournalLine(account_code="1100", debit="1070.00", credit="0"),
            JournalLine(account_code="4000", debit="0", credit="1000.00"),
            JournalLine(account_code="2101", debit="0", credit="70.00"),
        ],
    )
