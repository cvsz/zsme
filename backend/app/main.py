from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.domain.ledger import JournalEntry, JournalLine
from app.domains.ledger.api import router as ledger_router

app = FastAPI(
    title="ZSME Accounting API",
    version="0.1.0",
    description="Thailand-first SME accounting API with double-entry accounting invariants.",
)

app.include_router(auth_router)
app.include_router(ledger_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "zsme-api"}


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
