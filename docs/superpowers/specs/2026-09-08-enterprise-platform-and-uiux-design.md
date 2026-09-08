# ZSME Enterprise Platform and UI/UX Design

Date: 2026-09-08
Status: Draft - awaiting user review
Scope: Full ZSME enterprise platform, all application surfaces, and production-readiness controls

## 1. Intent and boundary

ZSME will become a Thailand-first, self-hostable SME finance and operations platform with an accounting-safe core. The product will cover the workflows observed in the read-only SMEMOVE benchmark review while remaining an independent implementation: no third-party source code, branding, copy, assets, or layout will be copied.

The implementation is a long-lived program, not a single release. Every domain will be delivered as a complete vertical slice with persistence, authorization, auditability, UI states, tests, documentation, migration safety, and operational evidence. A module is not considered production-ready because its page renders or its happy-path test passes.

Production-grade claims will be separated into four evidence levels:

1. Local: reproducible tests, lint, type checks, security checks, container build, migration and smoke evidence.
2. Hosted CI: required checks on the exact commit and artifact.
3. Staging: deployed artifact, migration rehearsal, browser flows, backup/restore, performance and failure drills.
4. Production: approved rollout, monitoring, rollback readiness, and post-deploy evidence.

No deployment, release publication, tag creation, data import, or external-system mutation is included automatically in repository implementation work.

## 2. Product principles

- The ledger is the financial system of record.
- Financial effects are created atomically with their source document or payment.
- Posted entries cannot be edited or deleted; corrections use reversal or adjustment workflows.
- Every persisted business record is scoped to a tenant and organization boundary.
- Every externally retried mutation is idempotent and every asynchronous effect is replay-safe.
- Thai statutory behavior is effective-dated, versioned, testable, and released only after current official requirements are validated.
- A disabled or unconfigured integration reports its real state; it never presents a fake success state.
- The interface optimizes for trust, clarity, keyboard use, dense business data, and safe financial actions.
- Mobile views prioritize review, approval, search, and capture; desktop views expose dense operational workspaces.

## 3. Architecture decision

### 3.1 Recommended approach: modular monolith with replaceable adapters

ZSME will use a modular monolith initially:

- Backend: FastAPI, Python 3.12+, SQLAlchemy 2, Alembic, PostgreSQL.
- Frontend: Next.js App Router, TypeScript, Tailwind CSS, accessible headless primitives, and a shared ZSME component library.
- Jobs and delivery: Redis-backed worker process plus a transactional outbox/inbox model.
- Files: object-storage abstraction with a local development provider and S3-compatible production provider.
- Integrations: explicit provider adapters behind stable contracts; no provider-specific behavior in core accounting modules.
- Deployment: Docker Compose for development and reproducible CI; a production container and Kubernetes/Helm-compatible deployment package after staging evidence exists.

Modules own their domain models, services, policies, routes, events, and tests. They communicate through typed application interfaces and domain events rather than direct table access across boundaries. The ledger, identity, tenant policy, audit, idempotency, and document-number services are platform capabilities used by all modules.

This approach preserves transactional consistency for financial workflows, keeps the first operational deployment manageable, and leaves clear extraction seams if a domain later requires an independent service.

### 3.2 Alternatives rejected for the first program increment

- Microservices from day one: stronger independent scaling boundaries, but excessive operational overhead and difficult cross-service financial transactions before the domain model is proven.
- CRUD-first generated admin: faster page count, but weak workflow semantics, poor auditability, inconsistent permissions, and a generic UI that would not be suitable for financial operations.

## 4. Repository shape

The implementation will evolve the current bootstrap without breaking the existing API contract:

```text
backend/
  app/
    api/                 # versioned HTTP routers, dependencies, error mapping
    core/                # settings, security, tenant context, clocks, IDs
    db/                  # engine, sessions, migrations, transaction helpers
    domains/
      identity/
      organizations/
      partners/
      catalog/
      ledger/
      sales/
      receivables/
      purchasing/
      payables/
      expenses/
      inventory/
      banking/
      tax/
      assets/
      payroll/
      workforce/
      pos/
      manufacturing/
      documents/
      reporting/
      integrations/
      notifications/
      audit/
    workers/             # jobs, outbox delivery, scheduled tasks
    observability/       # logging, metrics, tracing, health probes
  tests/
    unit/
    integration/
    contract/
    security/
    property/
frontend/
  app/                    # auth, tenant shell, module routes
  components/
    design-system/
    data-grid/
    forms/
    documents/
    charts/
  lib/                    # API client, auth, locale, feature flags
  tests/                  # Playwright, accessibility, visual contracts
docs/
  architecture/
  api/
  runbooks/
  superpowers/specs/
infra/
  compose/
  helm/
  observability/
```

The current `backend/app/domain/ledger.py` validation behavior remains the first domain invariant and will be moved behind the persistent ledger boundary with regression coverage before new document posting is enabled.

## 5. Domain and page inventory

Every module receives a consistent page set: overview where useful, searchable list, create/edit form, detail workspace, approval/history view, export/print action where applicable, empty/loading/error/permission states, and an audit panel for material changes.

### 5.1 Platform, identity, and administration

- Sign in, sign out, password reset, MFA enrollment/challenge, OIDC callback, session management.
- Organization/company selector, branch selector, fiscal year and locale settings.
- Company profile, tax registration, numbering, document templates, notification rules, payment channels.
- Users, roles, permission matrix, sensitive-data permissions, API keys, service accounts, webhook credentials.
- Audit explorer, import/export jobs, background-job monitor, integration health, usage/plan, system health.

### 5.2 Dashboard and work management

- Executive dashboard: cash, revenue, receivables, payables, tax exposure, margin, alerts.
- Operator dashboard: pending approvals, overdue documents, unmatched bank items, low stock, failed jobs.
- Task inbox, approval queue, saved views, command palette, global search, recent records, notification center.

### 5.3 Partners and catalog

- Customers, suppliers, contacts, segments, credit terms, billing/receipt schedules, addresses and branches.
- Products, services, expenses, categories, units of measure, price lists, tax mapping, SKU/barcode/serial settings.
- Product detail includes accounting mappings, inventory policy, attachments, images, price history, and change history.

### 5.4 Accounting and financial control

- Chart of accounts tree and account detail.
- Journals, journal entry detail, recurring journals, opening balances, closing entries.
- Fiscal periods, lock/reopen workflow, approval history, reversal and adjustment wizard.
- Payment channels, cash accounts, fixed assets, depreciation schedules, account mapping rules.
- Trial balance, general ledger, balance sheet, profit and loss, cash flow, audit trail.

### 5.5 Sales, AR, and collection

- Quotations, sales orders, billing/delivery documents, tax invoices, abbreviated tax invoices.
- Receipts, deposits, payment allocations, credit notes, customer statements, aged receivables.
- Approval workflow, installment/progress billing, delivery status, collection worklist, customer communication.

### 5.6 Purchasing, AP, and expenses

- Purchase requests, purchase orders, goods receipts, vendor bills, debit/credit notes.
- Expenses, recurring expenses, payment vouchers, supplier deposits, cheque register.
- Withholding-tax documents, approval queues, payment allocation, aged payables, supplier statements.

### 5.7 Banking and reconciliation

- Bank/cash accounts, statement import, import mapping, duplicate detection, transfers.
- Matching workspace with deterministic matches, suggested matches, user confirmation, exceptions, reconciliation close.
- Reconciliation history, statement attachments, cash forecast, failed import/job detail.

### 5.8 Inventory, warehouse, and manufacturing

- Warehouses, locations, stock on hand, reservations, movements, transfers, stock counts, adjustments.
- FIFO/valuation views, serial and lot tracking, barcode capture, reorder rules, product transformation.
- BOMs, production orders, material issue, finished output, WIP, production cost and variance.

### 5.9 Assets, payroll, and workforce

- Asset register, acquisition, capitalization, depreciation, custody, transfer, disposal.
- Employees, departments, compensation components, payroll runs, approval, payment, payslips, deductions.
- Attendance, leave, calendars, overtime, commissions, social security, provident fund, student-loan deductions.

### 5.10 Tax, statutory, and electronic documents

- VAT configuration, tax register, input/output VAT, VAT reports, tax period close.
- WHT rates and certificates, P.N.D.1/3/53/1 Kor exports, P.P.30/P.P.36 exports, Social Security exports.
- e-Tax/e-Receipt configuration, signing/provider adapter state, submission queue, response/error history.
- Effective-dated rule versions, official-source validation record, document retention and download center.

### 5.11 POS, channels, and integrations

- POS sessions, tills, sales, returns, tax-invoice variants, cashier permissions and end-of-day close.
- Sales channels, store connections, marketplace connections, order sync, fulfillment, fees, refunds, settlement.
- Integration catalog, connection setup, sync status, webhook deliveries, retry/replay, mapping and reconciliation.

### 5.12 Documents, reporting, and communications

- Document template/theme editor, logo/signature/stamp settings, numbering, PDF preview, print/download.
- Attachments, secure file access, integrity metadata, email delivery, notification templates and delivery log.
- Financial, sales, purchasing, inventory, payroll, tax, banking, audit and management reports.
- Report builder with saved reports, filters, grouping, drill-down, exports, scheduled delivery and permission-aware data.

## 6. Financial data model and invariants

All mutable records use UUID identifiers, UTC timestamps, an explicit organization/tenant scope, optimistic versioning, created/updated actors, and soft deletion only where business semantics permit it. Posted financial records are never soft-deleted as a substitute for correction.

Money uses fixed-precision `NUMERIC` values with explicit currency and rounding policy. Storage uses Gregorian dates and UTC timestamps; the UI renders Thai locale and Buddhist Era dates where configured, without mixing display dates into accounting calculations.

Core invariants:

1. A posted journal entry balances exactly.
2. Each journal line is debit or credit, never both and never neither.
3. Posted entries are immutable; reversal and adjustment entries preserve lineage.
4. Source document state and generated financial effects commit in one database transaction.
5. Locked periods reject posting except through an authorized, audited reopen flow.
6. Tenant, organization, branch, actor, source document, correlation ID, and posting ID are retained.
7. API mutations accept scoped idempotency keys with durable request/result records.
8. Document numbering is concurrency-safe and unique within configured scope.
9. Inventory, payroll, tax, payments, and settlement effects reconcile to their source records and ledger postings.
10. External callbacks, imports, and jobs are safe to retry and replay.

The database will enforce critical uniqueness, foreign keys, non-negative and one-sided journal line rules where practical, period locks, tenant scope constraints, and source/idempotency uniqueness. Application validation remains necessary for workflow and authorization rules.

## 7. Workflow and posting design

### 7.1 Order to cash

Draft quotation -> submitted -> approved -> invoice/delivery -> delivered/issued -> receipt or installment allocation -> closed. Approval and posting permissions are separate. Invoice posting creates receivable, revenue, and tax lines according to effective-dated mappings. Receipt posting reduces receivable and increases the selected cash/bank account. Credit notes reverse or adjust the original lineage rather than mutating posted totals.

### 7.2 Procure to pay

Purchase request -> approved PO -> goods receipt -> vendor bill -> WHT/payment voucher -> payment allocation -> closed. Inventory receipts and expenses use distinct posting strategies. Supplier balances, WHT, input VAT, payment channels, and inventory valuation remain traceable to source documents.

### 7.3 Reconciliation

Statement import -> normalize -> deduplicate -> deterministic match -> suggested match -> user confirmation -> reconcile close. Suggestions never post silently. Marketplace settlement separates gross sales, discounts, fees, refunds, tax/WHT components, and net cash before reconciliation.

### 7.4 Async document and integration work

A committed business transaction writes an outbox event. Workers deliver email, render documents, submit statutory/e-document payloads, or synchronize external data. Each attempt records status, retry count, provider response, correlation ID, and safe replay behavior. User-facing states are `not_configured`, `queued`, `processing`, `succeeded`, `failed`, or `needs_review`; no fake success state is allowed.

## 8. API contract

The API remains versioned under `/v1` and follows consistent conventions:

- OpenAPI-generated contract and typed frontend client.
- RFC 9457-style problem responses with stable error codes, field errors, correlation IDs, and safe messages.
- Cursor pagination, deterministic sorting, scoped filtering, field selection where useful, and export job endpoints for large results.
- `Idempotency-Key` required for financial posting, payment, imports, webhooks, and external side effects.
- ETags/version checks for mutable drafts and settings.
- Explicit authorization dependencies on every route and service boundary.
- Signed webhook delivery with replay window and delivery log.
- No endpoint exposes secrets, raw credentials, unredacted PII, or cross-tenant records.

## 9. Security and enterprise controls

- OIDC is the preferred enterprise authentication path; a local password adapter is limited to development and controlled self-hosted deployments.
- MFA supports TOTP and WebAuthn where the identity provider supports it.
- Short-lived access tokens, rotating refresh/session credentials, session revocation, device/session view, and secure cookie policy.
- RBAC is combined with organization, branch, module, action, and sensitive-data scopes.
- Tenant isolation is enforced in request context, repository queries, database constraints/policies where available, and cross-tenant tests.
- Secrets come from environment/secret-manager interfaces; credentials are never committed or logged.
- TLS at ingress, secure headers, CSP, CSRF protection for cookie-authenticated browser mutations, rate limits, request size limits, and abuse monitoring.
- Sensitive identifiers and documents use field/object encryption where required; access and downloads are audited.
- Dependency, container, secret, SAST, and SBOM checks run in CI with fail-closed policy for high-severity findings.

## 10. Enterprise UI/UX and theme

### 10.1 Visual direction

The theme is **Trustworthy Thai Enterprise Finance**: a data-dense operational dashboard with restrained motion, clear financial hierarchy, and an unmistakable blue data language with amber action emphasis. It should feel precise and calm during high-volume accounting work rather than decorative or playful.

The generated source of truth is `design-system/zsme-enterprise/MASTER.md`.

Core tokens:

- Primary blue `#1E40AF`; secondary blue `#3B82F6`.
- Action amber `#D97706`, used for high-value calls to action with verified contrast treatment.
- Background `#F8FAFC`; muted surface `#E9EEF6`; border `#DBEAFE`.
- Foreground `#1E3A8A`; destructive `#DC2626`; focus ring `#1E40AF`.
- Heading font Lexend; body font Source Sans 3 with Noto Sans Thai fallback for Thai glyph coverage.
- Spacing scale 4/8/16/24/32/48/64px, exposed as tokens and used consistently.
- Dark mode is the authenticated dashboard default; light mode is a complete user-selectable and print-friendly alternate. Both themes use semantic tokens, never raw colors inside feature components.

Fonts will be self-hosted or bundled with the web application for predictable rendering and privacy. Contrast is checked for normal text at WCAG AA thresholds and action/status colors are never the only signal.

### 10.2 Application shell

- Desktop: collapsible module sidebar, top command/search bar, tenant/branch/period context, notifications, help, and profile/session controls.
- Tablet: compact sidebar plus persistent context bar.
- Mobile: prioritized content, drawer navigation, bottom navigation limited to five high-frequency destinations, and full-screen document forms.
- Every route has a deep link, predictable back behavior, breadcrumbs where depth requires them, and route-level loading/error boundaries.

### 10.3 Core components

- Data grid: server-side pagination, column selection, saved views, keyboard navigation, row status, density toggle, export job, and mobile card fallback.
- Financial document workspace: summary header, status timeline, source/linked documents, editable draft sections, totals panel, posting/approval actions, attachments, and audit history.
- Forms: visible labels, Thai/English helper text, inline validation, grouped progressive disclosure, unsaved-change warning, field-level permissions, and safe confirmation for irreversible actions.
- Reports: KPI cards, accessible charts, tabular drill-down, filter chips, query state in URL, print/download/export jobs, and no-data explanations.
- Feedback: skeletons for loading, empty states with next action, retryable errors, optimistic updates only for non-financial UI state, and clear queued/processing status for async work.
- Icons: one consistent SVG icon family such as Lucide; no emoji used as interface icons.

### 10.4 Responsive and accessibility contract

- Mobile-first layout with breakpoints at 640, 768, 1024, 1280, and 1536px only when content needs them.
- Fluid containers, `rem` typography/spacing, no fixed-width page assumptions, and no horizontal page scroll.
- Touch targets are at least 44x44px with at least 8px separation.
- Body text is at least 1rem, line height supports Thai readability, and long labels wrap without clipping.
- Full keyboard navigation, visible focus, semantic landmarks, screen-reader labels, dialog focus management, and reduced-motion support.
- Check at 375, 414, 768, 1024, and 1440px with browser automation and visual regression snapshots.
- Tables and charts provide non-color equivalents, accessible names, keyboard drill-down, and text alternatives.

Motion is subtle and meaningful: 150-300ms state transitions, small 8-16px reveal offsets, no layout-shifting hover, and `prefers-reduced-motion` support. Financial status changes use explicit text and timeline transitions rather than distracting animation.

## 11. Reliability, observability, and operations

- Structured JSON logs with request ID, correlation ID, tenant-safe actor context, route, duration, outcome, and redaction.
- Metrics for request rate/errors/latency, database pool, job queues, outbox age, failed integrations, reconciliation backlog, and financial posting failures.
- OpenTelemetry traces across HTTP, database, workers, document rendering, and provider adapters.
- Liveness and readiness probes distinguish process health, dependency health, migration state, and degraded external integrations.
- Health endpoints never reveal credentials or sensitive business data.
- Database migrations are forward-safe, reviewed, reversible where possible, and rehearsed against a production-like snapshot.
- Automated encrypted backups, point-in-time recovery strategy, restore verification, retention policy, and documented RPO/RTO.
- Baseline targets: 99.9% monthly availability after HA deployment, RPO no worse than 15 minutes, RTO no worse than 1 hour, and p95 API latency below 500ms for normal reads/writes excluding long exports.
- Runbooks cover deploy, rollback, migration failure, worker backlog, provider outage, database restore, credential rotation, incident response, and tenant data export/deletion requests.

## 12. Quality and verification gates

Each vertical slice follows test-first development:

1. Write a focused behavior test.
2. Run it and record the expected failure.
3. Implement the smallest behavior.
4. Run the focused test and the full relevant suite.
5. Refactor only while green.

Required test layers:

- Domain unit and property tests for money, tax, document states, posting, reversal, permissions, and idempotency.
- PostgreSQL integration tests for constraints, transactions, migrations, tenant isolation, locks, and rollback.
- API contract tests for every route, problem response, pagination, authorization, and replay behavior.
- Browser end-to-end tests for each critical workflow and every permission-sensitive action.
- Accessibility tests and responsive visual regression at the defined breakpoints.
- Security tests for authentication, authorization, CSRF, rate limits, secret redaction, file access, and cross-tenant denial.
- Performance tests for list/report endpoints, posting, imports, worker queues, and concurrent numbering.
- Backup/restore and migration rehearsal tests.

CI gates will include formatting/lint, type checking, full tests, coverage floors with no unjustified regression, dependency audit, secret scan, SAST, container scan, SBOM generation, frontend build, browser tests, and artifact provenance. A green local suite does not replace hosted CI or staging evidence.

## 13. Delivery program

### Phase 0: engineering foundation

Repository structure, configuration contract, error model, logging, health/readiness, PostgreSQL/Alembic, test fixtures, CI quality gates, container hardening, design tokens, app shell, and route authorization skeleton.

Exit evidence: clean migration from empty database, health/readiness distinction, reproducible CI, secure configuration validation, responsive shell snapshots, and no cross-tenant context bypass.

### Phase 1: identity, tenancy, and accounting kernel

Organizations, branches, users, roles, permissions, audit, chart of accounts, fiscal periods, journals, posting, reversal, locks, numbering, idempotency, and opening balances.

Exit evidence: atomic posting tests, immutable-posting tests, period-lock tests, authorization matrix, tenant-isolation tests, migration/rollback rehearsal, and accounting reports from persisted ledger lines.

### Phase 2: master data and order to cash

Customers, services/products, quotations, invoices/delivery, receipts, deposits, credit notes, payment allocation, VAT mapping, document templates, and collection/report views.

Exit evidence: full quote-to-receipt browser flow, balanced journal lineage, approval permissions, duplicate-submit protection, PDF/print contract, accessible responsive pages, and AR/report reconciliation.

### Phase 3: procure to pay and tax core

Suppliers, purchase orders, goods receipts, bills, expenses, payment vouchers, WHT, input VAT, supplier balances, and tax registers.

Exit evidence: full purchase-to-payment flow, WHT/tax test vectors, payable reconciliation, approval and audit evidence, and export validation against versioned schemas.

### Phase 4: banking, cash, and inventory

Bank accounts, statement import, matching/reconciliation, cash transfers, cheques, warehouses, movements, counts, reservations, serial/lot/barcode, and valuation.

Exit evidence: idempotent import/replay, deterministic and confirmed matching, ledger/cash reconciliation, stock/GL reconciliation, concurrent numbering, and failure recovery.

### Phase 5: assets, payroll, workforce, POS, and channels

Fixed assets, depreciation, employees, payroll approval/payment, attendance/leave, statutory payroll outputs, POS, store connections, marketplace orders, and settlement reconciliation.

Exit evidence: approved payroll lineage, asset schedule reconciliation, POS close, provider outage/retry behavior, and settlement component reconciliation.

### Phase 6: electronic documents, reporting, automation, and hardening

e-Tax/e-Receipt adapters, official statutory exports, report builder, scheduled reports, notification center, document delivery, OCR/integration hooks, anomaly review, performance, HA, DR, and operational runbooks.

Exit evidence: staging deployment of the exact artifact, browser and accessibility suite, load results, security results, backup restore, rollback rehearsal, observability dashboards, and signed release review.

## 14. Stop conditions and scope controls

Work stops for review when any of the following occurs:

- A change would delete or rewrite user data, posted financial records, credentials, or external configuration.
- A migration cannot be demonstrated as safe on representative data.
- A financial invariant, tenant boundary, authorization rule, or audit guarantee fails.
- A provider contract, Thai statutory requirement, or production secret is missing and cannot be safely stubbed with an explicit disabled state.
- A visual change creates contrast, keyboard, responsive, or data-density regressions.
- A test failure cannot be localized without broadening scope or changing unrelated user work.

The implementation may continue with independent slices after a blocked integration, but it must record the blocker and never label the blocked capability production-ready.

## 15. Definition of done

A feature, page, or function is complete only when:

- Its domain behavior and failure behavior are specified.
- Persistence, migration, constraints, tenant scope, permissions, audit, and idempotency are implemented as applicable.
- Its UI includes loading, empty, error, denied, draft, submitted, approved, posted, reversed, and disabled/unconfigured states where applicable.
- Its APIs are documented and contract-tested.
- Its critical browser flow is covered at desktop and mobile breakpoints.
- Its financial/reporting/reconciliation impact is verified.
- Security, accessibility, performance, and observability checks are recorded.
- Rollback, recovery, and operational ownership are documented.
- Evidence identifies exactly what is local, CI, staging, or production; no stronger claim is made than the evidence supports.
