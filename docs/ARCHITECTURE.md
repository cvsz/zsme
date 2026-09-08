# ZSME Architecture

## 1. System intent

ZSME is a ledger-first accounting platform for Thai SMEs. The accounting ledger is the source of truth; operational documents such as invoices, bills, payments, tax documents, and bank transactions produce or reconcile ledger entries.

The target product scope now extends beyond accounting into a Thailand-first SME operating platform. Sales, purchasing, inventory, fixed assets, payroll, POS, marketplace, manufacturing, and statutory workflows must integrate through auditable accounting events rather than maintain disconnected financial totals.

## 2. Core domains

### Identity & tenancy
- Tenant/company
- Branch / establishment
- User
- Role and permission
- Department
- Warehouse-scoped permissions
- Sensitive payroll permission boundary
- Audit actor

### Organization & configuration
- Company profile
- Business-mode / feature configuration
- Payment channels
- Document numbering sequences
- Approval policies
- Document templates / presentation metadata

### Partner / CRM master data
- Customer
- Vendor / supplier
- Contact person
- Billing/shipping addresses
- Tax ID / branch metadata
- Payment and credit terms
- Salesperson ownership
- Partner attachments / notes / transaction history

### Product catalog
- Stockable product
- Non-stock product
- Service
- Raw material
- Consumable
- Expense item
- SKU / barcode
- Serial number
- Unit of measure / conversion
- Product variants and external SKU mapping
- Sales/purchase prices
- Tax/account mappings

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
- Manual/adjusting journal
- Recurring journal template
- Trial balance
- Audit trail

### Accounts receivable
- Customer
- Invoice
- Credit note
- Receipt
- Customer deposit / advance
- Payment allocation
- Partial settlement / residual balance
- Aged receivable

### Sales / order-to-cash
- Quotation
- Approval / confirmation
- Quotation validity and credit terms
- Foreign-currency quotation
- Project / salesperson reference
- Delivery / billing document
- Invoice
- Consolidated billing
- Receipt / consolidated receipt
- Full/abbreviated tax-document linkage
- Deposit application
- Installment / milestone billing
- Partial/multiple delivery
- Collection reminders
- PDF / email / print workflow

### POS / retail
- POS configuration by company/branch
- Cashier role
- POS session open/close
- Immediate sale/receipt
- Payment method
- Abbreviated tax invoice workflow
- Controlled conversion to full tax invoice
- Cash-drawer reconciliation hooks
- Warehouse stock decrement

### Accounts payable
- Vendor
- Vendor bill
- Vendor credit note
- Disbursement
- Supplier deposit / advance
- Payment allocation
- Aged payable

### Purchasing / procure-to-pay
- Purchase order
- Goods receipt
- Partial goods receipt
- Expense
- Recurring expense template
- Payment voucher
- Installment / batch payment
- Cheque register hooks
- Purchase attachments / approval
- Landed-cost linkage

### Inventory & warehouse
- Warehouse
- Warehouse/location permissions
- Stock movement ledger
- Goods receipt / issue
- Inventory transfer
- Two-step send/receive transfer
- Stock adjustment and stock count
- Reservation / available stock
- Serial number
- Barcode
- Unit conversion
- Assembly/disassembly
- Valuation layer
- FIFO costing baseline
- Inventory-to-GL reconciliation

### Manufacturing
- BOM and BOM versions
- Raw materials / consumables
- Direct labor / production time
- Manufacturing overhead
- Production order
- Material issue
- WIP hooks
- Finished-goods receipt
- Production costing
- Variance / scrap hooks

### Fixed assets
- Fixed-asset master
- Acquisition from purchasing
- Asset category
- Custodian / department / location
- Depreciation schedule
- Depreciation run / reversal
- Accumulated depreciation
- Transfer / borrow / return
- Disposal / write-off / sale
- Asset register and GL reconciliation

### Payroll & workforce
- Employee master
- Department / employment metadata
- Salary history
- Payroll period / run
- Earnings / deductions
- Commission profiles
- Payroll approval
- Payroll-to-GL posting
- Payroll payment batch
- Payslip
- Attendance / time clock
- Work calendar
- Leave request / approval

### Banking & reconciliation
- Bank account
- Cash account
- Statement
- Bank transaction
- CSV/XLSX import batch
- Matching rule
- Candidate match
- Reconciliation
- Internal account transfer
- Write-off / bank fee adjustment
- Cheque register
- Received/issued-cheque lifecycle hooks

### Thailand tax
- VAT configuration and effective dates
- VAT journal lines
- Full/abbreviated tax-invoice metadata
- Input/output VAT registers
- Input-VAT status workflow
- Withholding-tax rate/rule records
- Withholding-tax certificate records
- Payroll withholding data
- Social Security effective-dated rules
- Filing period state / submission evidence
- Versioned filing/export adapters

Do not hard-code statutory filing formats or rates into the core ledger. Keep government-specific schemas and effective-dated rules in versioned adapters so regulatory changes do not destabilize accounting invariants.

### Electronic documents
- e-Tax Invoice/e-Receipt metadata
- Issuance / transmission / failure status
- Retry state
- Provider adapter
- Certificate/key reference abstraction
- Signed payload / evidence hash
- Audit trail

### Marketplace & integrations
- Sales channel
- Connected store
- External credential reference
- Webhook/import batch
- Marketplace order normalization
- External SKU mapping
- Error/retry queue
- Settlement reconciliation
- Provider adapters such as Shopee / Lazada

The core sales and inventory domains must not depend directly on provider-specific schemas.

### Documents & communications
- Attachment
- Internal note
- Customer/vendor-visible note
- PDF rendering
- Email delivery
- Print metadata
- Configurable template/header/footer
- Original/copy rendering
- File integrity metadata
- Object-storage abstraction
- Retention/access audit hooks

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
10. Idempotency keys protect API posting/payment/import/integration operations from duplicate financial effects.
11. Inventory valuation movements must reconcile to stock movements and ledger postings.
12. Payroll postings must remain traceable to approved payroll-run/component data.
13. Statutory rules and rates are effective-dated and versioned.
14. Document numbering is concurrency-safe and unique within configured scope.
15. External callbacks/imports/webhooks are replay-safe.

## 4. API layout

- `/health` — runtime health
- `/v1/organizations/*` — companies, branches, users, roles, configuration
- `/v1/partners/*` — customers, suppliers, contacts
- `/v1/catalog/*` — products, services, UOM, SKU/barcode/serial configuration
- `/v1/accounting/*` — chart of accounts, journals, entries, posting
- `/v1/ar/*` — invoices, receipts, deposits, aged receivable
- `/v1/ap/*` — bills, payments, supplier deposits, aged payable
- `/v1/sales/*` — quotations, billing/delivery, collection workflows
- `/v1/purchasing/*` — purchase orders, goods receipts, expenses
- `/v1/inventory/*` — warehouses, stock movements, transfers, counts, valuation
- `/v1/manufacturing/*` — BOM, production orders, consumption/output
- `/v1/assets/*` — fixed assets, depreciation, custody, disposal
- `/v1/payroll/*` — payroll runs, payslips, deductions, postings
- `/v1/workforce/*` — attendance, leave, calendars
- `/v1/pos/*` — POS sessions and retail transactions
- `/v1/banking/*` — statements, imports, matching, reconciliation, cheques
- `/v1/tax/*` — VAT / withholding / statutory data and exports
- `/v1/e-documents/*` — e-Tax/e-Receipt lifecycle
- `/v1/integrations/*` — marketplace/provider connections and sync state
- `/v1/documents/*` — attachments, rendering, delivery
- `/v1/reports/*` — financial and operational reports

## 5. Target persistence model

PostgreSQL is the primary datastore. Core financial tables should use UUID primary keys, tenant/company keys, optimistic version fields where mutable drafts exist, and append-only audit records. Journal-entry posting should use database transactions and constraints in addition to application validation.

Accounting-critical operational workflows such as inventory valuation, payroll posting, document posting, deposit application, settlement, and reconciliation must execute transactionally with their generated ledger effects.

## 6. Reconciliation strategy

Matching should progress from deterministic to heuristic:

1. Exact reference + amount + partner
2. Exact amount + partner + date window
3. Invoice/payment reference tokens
4. User-defined reconciliation rules
5. Suggested matches requiring user confirmation

A suggested match must never silently alter the ledger unless it meets an explicitly configured auto-post policy.

Marketplace settlement reconciliation should separately normalize gross sales, discounts, fees, refunds, withholding/tax components where applicable, and net cash settlement before accounting reconciliation.

## 7. Reporting

Minimum production financial reporting surface:

- Trial Balance
- General Ledger
- Balance Sheet
- Profit & Loss
- Cash Flow Statement
- Aged Receivable
- Aged Payable
- VAT register/report
- Withholding reports
- Bank reconciliation
- Fixed-asset register
- Audit Trail

Operational reporting should later include:

- sales by period / salesperson / channel / product
- quotation conversion and collections
- stock on hand / reserved / available
- stock movement and valuation
- serial-number inventory
- warehouse transfers
- BOM/production cost and variance
- payroll register / payslip / department payroll
- attendance / leave
- expected receipts/payments and short-term cash forecast

Reports should support company, branch, date range, journal, account, partner, currency, document status, warehouse, salesperson, department and other domain-specific filters where applicable.

## 8. Security baseline

- Tenant isolation on every query and mutation
- Least-privilege RBAC
- Warehouse-scoped authorization
- Separate controls for sensitive payroll data
- No secrets committed to Git
- Structured audit log for financial and privileged mutations
- Rate limiting on auth/import/integration endpoints
- Backup + restore testing
- Encryption in transit
- Dependency and container scanning in CI
- Idempotency and webhook replay protection
- Attachment access control and integrity metadata
- Provider credentials stored only through a secret-management abstraction

## 9. Delivery sequence

### Phase 1 — Foundation
FastAPI service, tests, CI, Docker, PostgreSQL.

### Phase 2 — Ledger
Accounts, journals, periods, journal persistence, posting, reversal, locks.

### Phase 3 — Partners + AR/AP
Customers, vendors, invoices, bills, deposits, credit notes, payments and residual allocation.

### Phase 4 — Sales + purchasing documents
Quotation, billing/delivery, receipt, PO, goods receipt, approvals, installments and attachments.

### Phase 5 — Banking + cash
Statement imports, candidate matching, reconciliation, transfers, cheques and cash controls.

### Phase 6 — Thailand tax core
Versioned VAT/withholding primitives, effective-dated statutory rules and validated export adapters.

### Phase 7 — Inventory + warehouse
Catalog, movements, FIFO valuation, serial/barcode, multi-warehouse, transfer and counting.

### Phase 8 — Fixed assets
Acquisition, register, depreciation, custody and disposal.

### Phase 9 — Reporting
Financial, tax, sales, inventory, AR/AP and management reporting.

### Phase 10 — Payroll + workforce
Employees, payroll, Social Security, funds, withholding, payslips, attendance and leave.

### Phase 11 — POS + marketplace
Retail POS, tax-invoice variants, sales channels, marketplace integration and settlement reconciliation.

### Phase 12 — Manufacturing
BOM, production orders, material issue, WIP/finished goods and costing.

### Phase 13 — Electronic/statutory adapters
Current official filing/export adapters, e-Tax, bank/provider adapters.

### Phase 14 — Automation
OCR hooks, workflow rules, cash forecast, suggested reconciliation, alerts and anomaly detection.

### Phase 15 — Production hardening
RBAC verification, observability, backup/restore, migrations, security scans, performance, retention and release automation.

See `docs/SMEMOVE_FEATURE_BENCHMARK.md` for the detailed public-feature benchmark and backlog.