# ZSME Architecture

## 1. System intent

ZSME is a ledger-first accounting platform for Thai SMEs. The accounting ledger is the source of truth; operational documents such as invoices, bills, payments, tax documents, and bank transactions produce or reconcile ledger entries.

## 2. Core domains

### Identity & tenancy
- Tenant/company
- User
- Role and permission
- Audit actor

### Accounting master data
- Chart of accounts
- Journals
- Fiscal years and periods
- Currencies and exchange rates
- Taxes and tax mappings
- Payment terms

### General ledger
- Journal entry
- Journal line
- Posting / reversal
- Period lock
- Trial balance
- Audit trail

### Accounts receivable
- Customer
- Invoice
- Credit note
- Receipt
- Payment allocation
- Aged receivable

### Accounts payable
- Vendor
- Vendor bill
- Vendor credit note
- Disbursement
- Payment allocation
- Aged payable

### Banking & reconciliation
- Bank account
- Statement
- Bank transaction
- Matching rule
- Reconciliation
- Write-off / bank fee adjustment

### Thailand tax
- VAT configuration and VAT journal lines
- Tax invoice metadata
- Input/output VAT registers
- Withholding-tax certificate records
- Filing/export adapters

Do not hard-code statutory filing formats into the core ledger. Keep current government-specific schemas in versioned adapters so regulatory changes do not destabilize accounting invariants.

## 3. Accounting invariants

1. A posted journal entry must balance exactly: total debit equals total credit.
2. A journal line carries a debit or a credit, never both.
3. Posted entries are immutable. Corrections use reversal or adjusting entries.
4. Posting must be atomic: document state and generated journal entry commit in one database transaction.
5. Closed/locked periods reject new postings unless an authorized reopening workflow is used.
6. Every posting stores actor, tenant, source document, timestamps, and correlation identifiers for auditability.
7. Financial reports are derived from posted ledger lines, not duplicated mutable totals.
8. Money uses decimal/fixed precision; never binary floating point.
9. Tenant identifiers are mandatory on persisted business records and enforced at the data-access boundary.
10. Idempotency keys protect API posting/payment/import operations from duplicate financial effects.

## 4. API layout

- `/health` — runtime health
- `/v1/accounting/*` — chart of accounts, journals, entries, posting
- `/v1/ar/*` — customers, invoices, receipts, aged receivable
- `/v1/ap/*` — vendors, bills, payments, aged payable
- `/v1/banking/*` — statements, imports, matching, reconciliation
- `/v1/tax/*` — VAT / withholding data and exports
- `/v1/reports/*` — trial balance, GL, P&L, balance sheet, cash flow, audit trail

## 5. Target persistence model

PostgreSQL is the primary datastore. Core financial tables should use UUID primary keys, tenant/company keys, optimistic version fields where mutable drafts exist, and append-only audit records. Journal-entry posting should use database transactions and constraints in addition to application validation.

## 6. Reconciliation strategy

Matching should progress from deterministic to heuristic:

1. Exact reference + amount + partner
2. Exact amount + partner + date window
3. Invoice/payment reference tokens
4. User-defined reconciliation rules
5. Suggested matches requiring user confirmation

A suggested match must never silently alter the ledger unless it meets an explicitly configured auto-post policy.

## 7. Reporting

Minimum production reporting surface:

- Trial Balance
- General Ledger
- Balance Sheet
- Profit & Loss
- Cash Flow Statement
- Aged Receivable
- Aged Payable
- VAT register/report
- Audit Trail

Reports should support company, date range, journal, account, partner, currency, and posted/draft filters where applicable.

## 8. Security baseline

- Tenant isolation on every query and mutation
- Least-privilege RBAC
- No secrets committed to Git
- Structured audit log for financial mutations
- Rate limiting on auth/import endpoints
- Backup + restore testing
- Encryption in transit
- Dependency and container scanning in CI

## 9. Delivery sequence

### Phase 1 — Foundation
FastAPI service, tests, CI, Docker, PostgreSQL.

### Phase 2 — Ledger
Accounts, journals, periods, journal persistence, posting, reversal, locks.

### Phase 3 — AR/AP
Invoice/bill state machines and automatic journal generation.

### Phase 4 — Banking
Statement imports, candidate matching, reconciliation, partial payments.

### Phase 5 — Thailand tax
Versioned VAT/withholding primitives and statutory export adapters validated against current official requirements.

### Phase 6 — Reporting
Ledger-derived financial reports and exports.

### Phase 7 — Product UX
Next.js dashboard, workflows, search, attachments, localization.

### Phase 8 — Production hardening
RBAC, observability, backup/restore, migrations, security scans, deployment automation.
