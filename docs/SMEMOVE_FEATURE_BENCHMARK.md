# ZSME — SMEMOVE Feature Benchmark & Expansion Backlog

Status: product research / implementation backlog
Reviewed: 2026-09-08

## 1. Purpose and boundary

This document inventories useful SME workflows visible in the public SMEMOVE help center and translates them into independent ZSME product requirements.

ZSME must not copy SMEMOVE source code, proprietary assets, wording, screen layouts, branding, or implementation details. SMEMOVE is used only as a public functional benchmark. ZSME remains ledger-first: operational documents create, reverse, settle, or reconcile accounting events through auditable double-entry postings.

Primary public benchmark categories reviewed:

- https://help.smemove.com/
- https://help.smemove.com/article-categories/ออกใบเสนอราคา-ใบวางบิล/
- https://help.smemove.com/article-categories/buy-expense/
- https://help.smemove.com/article-categories/สินค้า/
- https://help.smemove.com/article-categories/payroll/
- https://help.smemove.com/article-categories/accounting/
- https://help.smemove.com/article-categories/inventory-contact/
- https://help.smemove.com/article-categories/report/
- https://help.smemove.com/article-categories/account-management/

Thailand statutory requirements must be validated against current Revenue Department, Social Security Office, ETDA, banking, and other authoritative specifications before production filing/submission.

## 2. Executive gap summary

The current ZSME architecture already covers the ledger, AR/AP, banking/reconciliation, VAT/WHT primitives, core financial reports, tenancy, RBAC, auditability, and production hardening.

The largest missing product domains exposed by the SMEMOVE benchmark are:

1. complete sales-document lifecycle and approval workflow
2. POS and marketplace/e-commerce operations
3. purchasing, receiving, expense, cheque, installment, and landed-cost workflows
4. product catalog, serial numbers, barcode, stock reservations, multi-warehouse and transfers
5. manufacturing/BOM and production costing
6. fixed-asset lifecycle and custody
7. payroll, employee master data, attendance, leave and Thailand payroll deductions
8. expanded Thai statutory filing/export adapters
9. document templates, numbering, signatures and configurable business workflows
10. management, operational, payroll and inventory reporting

## 3. Target module map

### 3.1 Organization, identity and configuration

Add:

- multi-company / multi-tenant company profile
- branch / establishment metadata
- business-mode configuration: trading, services, construction, manufacturing, retail/online
- user invitations
- role-based and permission-based access
- warehouse-scoped permissions
- payroll-sensitive permission boundaries
- per-user signature image / approval signature metadata
- sales-person assignment
- department master data
- configurable payment channels
- configurable document numbering sequences by company, branch, document type and fiscal period
- configurable document labels and presentation metadata
- configurable document themes/templates without changing accounting semantics
- feature flags for warehouse, POS, marketplace, manufacturing and payroll modules

Required controls:

- numbering sequences must be concurrency-safe
- renumbering a posted statutory document requires a controlled correction workflow
- permissions must be tenant-scoped and deny by default
- sensitive payroll data requires a separate permission domain

### 3.2 Partner / CRM master data

Add:

- customer master
- supplier/vendor master
- unified business-partner model where appropriate
- tax ID and branch information
- billing and shipping addresses
- contact persons
- payment terms / credit terms
- credit limit hooks
- sales-person ownership
- partner notes and attachments
- import from CSV/XLSX
- duplicate detection and merge workflow
- transaction history by partner

### 3.3 Product and service master

Add:

- stockable product
- non-stock product
- service item
- raw material
- consumable
- expense item
- SKU / internal product code
- marketplace SKU mapping
- parent/model SKU mapping for variants
- barcode
- serial-number tracking
- unit of measure
- unit conversion
- sales price / purchase price
- accounting mappings per product/category
- tax mappings per product/category
- product attachments and notes
- purchase/sales history
- opening quantity and opening cost import

### 3.4 Sales / order-to-cash

Add full document state machines for:

- quotation
- quotation approval / confirmation
- payment terms and credit terms
- quotation validity period
- foreign currency and exchange rate
- sales-person assignment
- project/cost-center reference
- file attachments and internal notes
- customer-facing notes
- quotation to invoice conversion
- quotation to billing/delivery workflow
- delivery note
- invoice / billing note
- consolidated billing by customer and date range
- receipt
- consolidated receipt
- tax invoice attached to invoice/receipt or issued as a separate document
- deposit / advance receipt
- deposit application against later invoices
- sales credit note
- partial payment
- installment schedule
- multiple billing milestones from one quotation
- partial/multiple delivery
- cheque-receipt tracking
- collection reminders / billing reminders
- document PDF generation
- original/copy rendering metadata
- email delivery
- print workflow
- document attachments

Accounting requirements:

- every posting transition must be idempotent
- deposits must post to advance/deferred accounts until recognized
- partial settlement must preserve open residual amounts
- credit notes must reference original documents where required
- foreign-currency documents must retain document currency, functional currency and rate provenance

### 3.5 POS / retail sales

Add:

- POS configuration by company/branch
- cashier role and permissions
- restricted visibility for cost/margin data
- quick sale / immediate receipt workflow
- payment-method selection
- abbreviated tax invoice workflow
- conversion from abbreviated to full tax invoice under a controlled process
- shift/session open-close model
- cash-drawer reconciliation hooks
- POS sales-to-ledger posting
- stock decrement by warehouse/location
- offline/retry design as a later enhancement

### 3.6 Marketplace / e-commerce integration

Add an integration framework first, then adapters for supported marketplaces.

Capabilities:

- sales channel master
- store connection record
- OAuth/token lifecycle abstraction
- order import
- manual CSV/XLSX order import fallback
- marketplace SKU to ZSME SKU mapping
- parent/variant SKU mapping
- automatic order normalization
- automatic sales document generation policy
- abbreviated tax invoice generation policy where legally applicable
- stock availability validation
- serial-number exception handling
- rejected/error order queue
- retry after data correction
- integration audit log
- webhook ingestion with idempotency
- rate-limit handling
- store-level reconciliation of gross sales, fees, discounts, refunds and settlements

Initial benchmark adapters:

- Shopee
- Lazada

Do not couple the core sales domain to any marketplace-specific schema.

### 3.7 Purchasing / procure-to-pay

Add:

- purchase requisition as an optional ZSME extension
- purchase order
- supplier quotation reference
- goods receipt
- partial goods receipt
- vendor invoice / vendor bill
- purchase credit note
- payment voucher
- payment approval
- withholding-tax certificate linkage
- expense record
- cash-basis expense workflow
- accrual/payable expense workflow
- recurring expense template
- batch/consolidated expense payment
- installment payment schedule
- cheque printing metadata / cheque register
- receipt-voucher / internal payment evidence where required by workflow
- supplier deposit / advance payment
- application of supplier deposit to bills/receipts
- attachments such as supplier invoice, tax invoice, transfer slip and cheque evidence

### 3.8 Import purchasing and landed cost

Add:

- foreign-currency purchase order
- explicit exchange-rate capture
- freight
- customs duty
- import VAT
- insurance
- brokerage/handling fees
- other import charges
- landed-cost allocation across received items
- configurable allocation basis: quantity, value, weight, volume or manual
- resulting inventory cost adjustment
- audit trail from landed-cost component to resulting unit cost

### 3.9 Inventory / warehouse management

Add:

- warehouse master
- multiple warehouses per company
- location/bin abstraction as a later extension
- warehouse responsible users
- warehouse-scoped permissions
- goods receipt into warehouse
- delivery/issue from warehouse
- inventory transfer document
- transfer send/receive two-step workflow
- stock transfer in-transit state
- stock adjustment
- stock count / cycle count
- reservation / allocated quantity
- available-to-promise quantity
- serial-number lifecycle
- barcode scanning API/UI
- unit conversion
- assemble/disassemble product conversion
- stock movement ledger
- stock valuation layer
- FIFO costing baseline
- negative-stock policy
- reorder-point hooks
- inventory import/export
- warehouse closure/disable workflow that preserves historical movements

Accounting requirements:

- inventory quantity and valuation movements must be traceable to source documents
- stock valuation and GL inventory balances must be reconcilable
- posted movements must not be silently edited

### 3.10 Manufacturing / BOM

Add:

- bill of materials (BOM)
- BOM versioning
- raw materials
- consumables
- direct labor
- production time
- manufacturing overhead
- production order
- material issue
- finished-goods receipt
- production variance hooks
- component substitution policy
- scrap/waste hooks
- assembly and disassembly
- production costing
- downloadable/printable production order

Accounting requirements:

- material consumption, WIP and finished-goods valuation must reconcile to the ledger
- BOM change history must be retained
- production completion must be transactional with inventory movements

### 3.11 Fixed assets

Add:

- fixed-asset master
- asset acquisition from purchase documents
- bulk asset import
- asset category
- custodian / department / location
- depreciation start date
- useful life
- residual value
- configurable depreciation method
- automated depreciation schedule
- manual depreciation run with approval
- depreciation reversal/correction
- accumulated depreciation
- asset transfer / custody movement
- borrow/return workflow
- disposal / write-off / sale of asset
- impairment hook
- fixed-asset register and reconciliation to GL

### 3.12 Payroll and HR master data

Add:

- employee master
- department
- employment type
- Thai / foreign employee metadata where legally necessary
- salary history
- payroll period
- earnings components
- deduction components
- overtime/allowance hooks
- multiple commission profiles
- temporary-worker withholding workflow
- payroll batch calculation
- payroll approval
- payroll posting to GL
- payroll payment batch
- payslip generation
- continuous/batch payslip print/export
- payroll history
- employee-related document generation
- confidential executive-payroll permission boundary

Thailand-specific payroll primitives:

- Social Security contribution configuration with effective dates and caps
- provident fund
- Student Loan Fund (กยศ.) deduction import/workflow
- employee withholding tax
- year-end withholding certificate (50 ทวิ) data
- P.N.D.1 / P.N.D.1 Kor (ภ.ง.ด.1 / ภ.ง.ด.1ก) export adapter

Bank payment adapters can later support bank-specific payroll files such as SCB/KBank without coupling payroll calculation to a bank format.

### 3.13 Attendance, leave and workforce operations

Add:

- attendance/time-clock event
- clock-in / clock-out
- work calendar
- lateness
- absence
- leave request
- leave approval
- approval notification email
- attendance summary report
- attendance-to-payroll integration hooks
- mobile/time-clock integration API

Do not make time-clock data the only source for payroll; payroll input rules must be explicit and reviewable.

### 3.14 Banking, cash and reconciliation

Existing ZSME banking architecture should be extended with:

- bank-account master
- cash account master
- bank-statement import templates
- bank-statement CSV/XLSX import
- import validation preview
- unmatched transaction queue
- matching candidates
- exact/manual matching
- one-to-many and many-to-one matching
- bank transfer between internal accounts
- bank fees and settlement differences
- cheque register
- received-cheque lifecycle
- issued-cheque lifecycle
- payment-channel mapping
- reconciliation status and audit history
- opening/closing bank reconciliation reports

Future enhancement:

- bank API/Open Banking adapter framework where supported and lawful

### 3.15 Thailand VAT and tax documents

Extend current VAT primitives with:

- VAT rate configuration with effective dates
- VAT per document line
- mixed VAT rates within one document
- free-item / promotional-item tax treatment metadata
- output VAT register
- input VAT register
- full tax invoice
- abbreviated tax invoice
- controlled abbreviated-to-full tax invoice conversion
- tax invoice issue timing policy by configured business workflow
- duplicate tax-invoice detection
- input-VAT status workflow, including current claim, deferred/right-reserved and non-creditable states
- purchase tax-invoice attachment
- VAT reconciliation to GL
- P.P.30 (ภ.พ.30) reporting/export adapter

Statutory semantics must be validated against current official Revenue Department rules before production use.

### 3.16 Withholding tax and statutory filing adapters

Add:

- withholding-tax rate table with effective dates
- withholding rules by payment/service category
- withholding certificate generation metadata
- supplier withholding workflow
- employee withholding workflow
- withholding payable reconciliation
- P.N.D.1 / 3 / 53 export adapters
- P.N.D.1 Kor annual export adapter
- 50 Bis (50 ทวิ) certificate data/output
- RD Prep-compatible export adapters where official specifications permit
- statutory filing period status
- submission evidence attachment
- filing lock and amendment workflow

### 3.17 Social Security and employment remittance

Add:

- effective-dated contribution rules
- employee contribution
- employer contribution
- caps/minimums as versioned rules
- remittance report
- Social Security online-submission export adapter where supported by official specification
- payment/reconciliation to Social Security payable account

Never hard-code current rates indefinitely; every statutory rate must be effective-dated and versioned.

### 3.18 e-Tax / electronic documents

Add an electronic-document adapter layer:

- e-Tax Invoice/e-Receipt document model
- issuance status
- transmission status
- failure/retry status
- immutable signed payload hash / evidence metadata
- e-Tax Invoice by Email adapter where still supported by current official requirements
- future provider adapters
- certificate/key reference abstraction without storing private keys in application tables
- audit event trail

Implementation must follow current ETDA/Revenue Department requirements, not a historical vendor workflow.

### 3.19 Accounting and period close

Keep the existing ledger design and add application workflows for:

- hierarchical chart of accounts
- control/header accounts that cannot receive direct postings
- manual journal entry
- adjusting journal entry
- recurring journal template
- accruals
- accrued income
- deferred/unearned income
- prepaid expense
- accrued expense
- bad-debt allowance
- depreciation
- inventory adjustment
- FX revaluation hooks
- month-end checklist
- year-end closing checklist
- retained earnings / profit closing
- fiscal-year lock
- tax-period lock
- reopening workflow with authorization and audit log
- account activity drill-down from reports

### 3.20 Reporting and management dashboard

Financial reports:

- company health / executive KPI dashboard
- Balance Sheet
- Profit & Loss
- Cash Flow Statement
- Trial Balance
- General Ledger
- Journal report
- AR aging
- AP aging
- bank reconciliation
- fixed-asset register
- VAT reports
- withholding reports
- audit trail

Sales/CRM reports:

- sales by period
- sales by salesperson
- sales by channel
- sales by product/category
- customer analysis
- quotation conversion
- outstanding collection
- deposit balance

Inventory/manufacturing reports:

- stock on hand
- reserved / available stock
- serial-number inventory
- stock movement
- inventory valuation
- best-selling products
- dead/slow stock
- warehouse transfer status
- BOM cost
- production order
- production variance

Payroll/HR reports:

- payroll register
- payslip history
- department payroll
- commission report
- employee tax/withholding
- Social Security
- attendance summary
- clock-in/out detail
- leave summary

Cash-management reports:

- expected receipts/payments
- short-term cash forecast
- cheque due-date report
- unpaid/overdue AR/AP

Every financial report must drill to immutable source postings/documents and support export where appropriate.

### 3.21 Documents, files and communications

Add a shared document service:

- attachments on operational documents
- internal notes
- customer/vendor-visible notes
- PDF generation
- email delivery
- print rendering
- document original/copy label
- configurable logo/theme/header/footer
- user signature rendering
- file integrity hash
- virus scanning hook
- object-storage abstraction
- retention policy
- access audit

### 3.22 Import/export framework

Add a generic import pipeline:

- CSV/XLSX template download
- staged upload
- schema validation
- dry-run preview
- row-level errors
- duplicate detection
- idempotency key/import batch ID
- partial vs atomic import policy
- retry corrected rows
- immutable import audit

Initial import targets:

- customers/vendors
- products
- opening inventory
- fixed assets
- bank statements
- marketplace orders
- payroll deduction inputs

### 3.23 Notifications and workflow automation

Add:

- approval task
- due-date reminder
- quotation expiration reminder
- billing reminder
- collection reminder
- cheque due reminder
- inventory exception
- integration failure notification
- leave approval notification
- payroll approval notification
- tax filing due reminder

Delivery channels:

- in-app
- email
- webhook

Future:

- LINE notification adapter

## 4. Proposed priority

### P0 — accounting-safe MVP

Must land before broad ERP expansion:

1. PostgreSQL ledger persistence
2. chart of accounts and journals
3. fiscal periods and locks
4. posting/reversal
5. customer/vendor master
6. invoice/vendor bill
7. receipt/disbursement
8. payment allocation
9. VAT/WHT primitives
10. bank import/reconciliation
11. core financial reports
12. audit trail/RBAC/tenant isolation

### P1 — Thai SME operational core

1. quotation -> invoice -> receipt lifecycle
2. purchase order -> receipt -> vendor bill -> payment
3. deposits and credit notes
4. product catalog
5. inventory movement and FIFO valuation
6. serial number and barcode
7. multi-warehouse transfer
8. fixed assets and depreciation
9. document PDF/email/templates/numbering
10. recurring expenses
11. cheque register
12. management/sales/inventory reports

### P2 — Thailand business suite

1. payroll
2. Social Security
3. provident fund / กยศ.
4. employee WHT and annual certificates
5. attendance/leave
6. POS
7. abbreviated/full tax invoice workflows
8. statutory export adapters: P.P.30, P.N.D.1/3/53/1 Kor, 50 Bis
9. e-Tax adapter
10. marketplace framework and Shopee/Lazada adapters

### P3 — manufacturing and advanced automation

1. BOM
2. production orders
3. production costing / WIP
4. landed cost
5. stock planning/reorder
6. cash forecast
7. automated reconciliation suggestions
8. integration rules and workflow engine
9. anomaly detection / duplicate-document detection
10. OCR/document ingestion hooks

## 5. Suggested service/domain boundaries

Recommended internal modules:

- identity
- organizations
- partners
- catalog
- sales
- pos
- purchasing
- expenses
- inventory
- manufacturing
- assets
- payroll
- workforce
- ledger
- banking
- tax
- compliance_adapters
- reporting
- documents
- integrations
- notifications
- audit

A modular monolith is preferred initially. Separate services only when operational scale or security boundaries justify the complexity.

## 6. Cross-cutting invariants

1. All financial effects route through the ledger.
2. Posted journal entries are immutable; corrections use reversal/adjustment.
3. Operational document posting is atomic with generated ledger entries.
4. Inventory value changes are traceable to stock movements and GL postings.
5. Payroll posting is traceable to payroll run, employee/component totals, and approval actor.
6. Statutory schemas/rates are effective-dated and versioned.
7. External integration callbacks/imports are idempotent.
8. Tenant/company scope is mandatory at every persistence boundary.
9. Document numbers are unique within configured statutory/business scope.
10. Permissions are evaluated for company, module, action and sensitive-data domain.
11. Money uses fixed-precision decimal arithmetic.
12. Source document, actor, timestamps, correlation ID and posting IDs are retained for audit.
13. Reports derive financial totals from posted ledger data rather than mutable duplicated balances.
14. Attachments and generated documents retain integrity and access audit metadata.

## 7. Recommended delivery sequence after current foundation PR

### Phase 2 — Ledger persistence
Accounts, journals, periods, entries/lines, posting, reversal, locks, migrations.

### Phase 3 — Partners + AR/AP
Customers, vendors, invoices, bills, credit notes, payments and residual allocation.

### Phase 4 — Sales + purchasing documents
Quotation, billing/delivery, receipt, PO, goods receipt, deposits, approvals and attachments.

### Phase 5 — Banking + cash
Statement import, reconciliation, transfers, cheque register and cash controls.

### Phase 6 — Thailand tax core
VAT, WHT, tax documents, tax registers and effective-dated rule engine.

### Phase 7 — Inventory + warehouse
Catalog, stock movement, FIFO valuation, SN/barcode, multi-warehouse, transfer and counting.

### Phase 8 — Fixed assets
Asset acquisition, register, depreciation, custody and disposal.

### Phase 9 — Reporting
Financial, operational, tax, AR/AP, inventory and management reports.

### Phase 10 — Payroll + workforce
Employee master, payroll, SSO, funds, WHT, payslips, attendance and leave.

### Phase 11 — POS + marketplace
Retail POS, tax-invoice variants, sales channels, marketplace integration and settlement reconciliation.

### Phase 12 — Manufacturing
BOM, production orders, material issue, WIP/finished goods and costing.

### Phase 13 — Statutory/e-document adapters
Current official filing/export adapters, e-Tax, provider/bank adapters.

### Phase 14 — Automation and intelligence
OCR hooks, rule engine, cash forecast, suggested reconciliation, alerts and anomaly detection.

### Phase 15 — Production hardening
Observability, backup/restore, DR, security scanning, performance, data retention, migration safety and release automation.

## 8. Definition of done for any new financial feature

A feature is not complete until it includes:

- domain invariants
- database constraints where applicable
- posting/reversal behavior
- tenant and RBAC checks
- audit events
- idempotency for externally triggered mutations
- tests for happy path and failure/rollback path
- migration strategy
- report/reconciliation impact
- attachment/document security where used
- API documentation
- regulatory validation if statutory behavior is involved

## 9. Product direction

The benchmark supports expanding ZSME from a narrow accounting application into a Thailand-first SME operating platform:

**Accounting + Sales + Purchase + Inventory + Assets + Payroll + POS + Manufacturing + Thai Compliance + Marketplace Integrations**

The sequencing should remain ledger-first so operational convenience never compromises accounting reproducibility, statutory traceability, or auditability.
