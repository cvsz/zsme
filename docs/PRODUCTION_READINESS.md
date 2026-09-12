# ZSME Production Readiness

Updated: 2026-09-12

This document is the canonical release-readiness view for the current repository. A green CI run is necessary but is not, by itself, production evidence.

## Implemented and CI-gated

- Tenant-scoped opaque sessions, RBAC and CSRF controls.
- Double-entry ledger with fiscal-period locks, idempotency and immutable posted records.
- AR/AP invoices and bills, receipts/disbursements, bank imports and reconciliation.
- Effective-dated tax-rate rules and VAT-rate enforcement for financial documents.
- Core financial reports, audit events and dashboard summaries.
- Base-currency-only posting guard until an explicit FX ledger exists.
- One-to-one payment-to-bank-transaction reconciliation invariant.
- SQLite fast tests plus PostgreSQL behavioral test execution.
- Container non-root runtime, health checks, dependency audit, frontend E2E/accessibility and image vulnerability scan.

## Release blockers still requiring implementation or external evidence

- Full multi-currency/FX accounting, realized/unrealized gain/loss and revaluation.
- Cash-account master and classified operating/investing/financing cash-flow mapping.
- Browser/API authentication surface separation and MFA/OIDC/session administration.
- Scheduled encrypted backups, retention automation and independently evidenced restore drills.
- HA deployment, production ingress/TLS, secrets management, metrics/traces/alerts and rollback evidence.
- Full Thailand statutory adapters and current Revenue Department/ETDA validation.
- Product/inventory, purchasing lifecycle, fixed assets, payroll/workforce, POS/marketplace and manufacturing domains.
- Signed/reproducible backend dependency lock and release artifact provenance.
- A repository LICENSE selected by the owner.

## Gate definitions

### Code complete
Implementation, migrations, authorization, auditability and automated tests exist.

### Staging evidenced
The release is deployed to a production-like environment and smoke, migration, security, accessibility and restore checks have recorded evidence.

### Production ready
Staging evidence is green; backup/restore, monitoring, incident response, rollback, secrets rotation and statutory requirements have named owners and tested procedures.

No module should be described as production-ready unless all applicable gates above are satisfied.
