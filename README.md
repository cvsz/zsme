# ZSME

**ZSME** is an open-source, Thailand-first SME accounting and business finance platform.

The project is designed as an independent implementation inspired by modern accounting workflows (not a copy of any third-party product or source code), with a focus on simple bookkeeping, auditability, and automation for Thai SMEs.

## Product goals

- Double-entry accounting with immutable posted journal entries
- Chart of accounts, journals, fiscal periods, and closing controls
- Customer invoices, credit notes, receipts, and accounts receivable
- Vendor bills, debit/credit adjustments, payments, and accounts payable
- Bank statement import and transaction reconciliation
- Thailand-ready tax primitives: VAT configuration, tax invoices, withholding-tax records, and tax reports
- Core financial reporting: Balance Sheet, Profit & Loss, General Ledger, Trial Balance, Cash Flow, Aged Receivable, Aged Payable, and Audit Trail
- Multi-company / multi-tenant architecture with RBAC
- API-first design and exportable accounting data
- Self-hostable deployment using PostgreSQL and containers

## Target stack

- **Frontend:** Next.js + TypeScript
- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **Cache / jobs:** Redis (optional in MVP)
- **Deployment:** Docker Compose first, Kubernetes-ready later
- **CI:** GitHub Actions

## Delivery phases

1. **Foundation** — repository, architecture, API health, CI, containers
2. **Accounting Core** — accounts, journals, periods, journal entries, posting rules
3. **AR / AP** — customers, invoices, vendor bills, credit notes, payment terms
4. **Payments & Reconciliation** — bank transactions, matching, partial/full reconciliation
5. **Thailand Tax** — VAT and withholding-tax workflow primitives and reports
6. **Financial Reports** — GL, TB, P&L, BS, cash flow, aged AR/AP, audit trail
7. **Automation** — imports, rules, OCR integration hooks, scheduled workflows
8. **Production Hardening** — RBAC, tenant isolation, observability, backup/restore, security controls

## Accounting invariants

ZSME treats the ledger as the system of record. Posted entries must always balance (`total debit == total credit`). Posted journal lines are not edited in place; corrections are made through reversals or adjusting entries. Business documents and payments ultimately map to journal entries so reports can be reproduced from the ledger and audit trail.

## Status

Repository bootstrap in progress.

> Regulatory note: Thailand-specific VAT, withholding tax, e-Tax Invoice/e-Receipt, filing formats, and statutory retention requirements must be validated against current Revenue Department / ETDA requirements before production filing or submission.

## License

License to be selected before public production release.
