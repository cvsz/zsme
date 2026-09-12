from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.access import router as access_router
from app.api.auth import router as auth_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.organizations import router as organizations_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.domain.ledger import JournalEntry, JournalLine
from app.domains.accounting.api import router as accounting_master_router
from app.domains.audit.api import router as audit_router
from app.domains.banking.api import router as banking_router
from app.domains.dashboard.api import router as dashboard_router
from app.domains.documents.api import router as documents_router
from app.domains.ledger.api import router as ledger_router
from app.domains.partners.api import router as partners_router
from app.domains.payments.api import router as payments_router
from app.domains.reports.api import router as reports_router
from app.domains.tax.api import router as tax_router
from app.observability.logging import configure_logging

app = FastAPI(
    title="ZSME Accounting API",
    version="0.1.0",
    description="Thailand-first SME accounting API with double-entry accounting invariants.",
)

configure_logging()
register_exception_handlers(app)
cors_origins = get_settings().cors_origin_list
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-ID",
            "X-CSRF-Token",
        ],
        expose_headers=["X-Correlation-ID"],
    )
app.include_router(access_router)
app.include_router(auth_router)
app.include_router(ledger_router)
app.include_router(health_router)
app.include_router(organizations_router)
app.include_router(search_router)
app.include_router(partners_router)
app.include_router(documents_router)
app.include_router(accounting_master_router)
app.include_router(reports_router)
app.include_router(payments_router)
app.include_router(tax_router)
app.include_router(banking_router)
app.include_router(audit_router)
app.include_router(dashboard_router)


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
