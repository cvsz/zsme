import {
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  CheckCircle2,
  CircleAlert,
  FileCheck2,
  FileUp,
  Filter,
  Landmark,
  Link2,
  LockKeyhole,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
} from "lucide-react";
import Link from "next/link";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";

const workflow = [
  { label: "Import", detail: "Bring in a signed statement or provider feed", icon: UploadCloud },
  { label: "Validate", detail: "Check dates, amounts and duplicate identifiers", icon: ShieldCheck },
  { label: "Match", detail: "Link movements to posted receipts or disbursements", icon: Link2 },
  { label: "Reconcile", detail: "Commit an auditable bank-to-ledger result", icon: CheckCircle2 },
] as const;

const controls = [
  { label: "Statement intake", detail: "CSV, OFX and provider adapters will use a committed import batch.", icon: FileUp },
  { label: "Duplicate protection", detail: "External transaction IDs are unique per bank account.", icon: ShieldCheck },
  { label: "Signed movement", detail: "Positive and negative amounts determine receipt or disbursement direction.", icon: Banknote },
  { label: "Immutable source", detail: "Imported descriptions, dates and amounts cannot be edited after ingestion.", icon: LockKeyhole },
] as const;

export function BankingWorkbench() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Cash control</p>
          <h1 className="page-title">Banking & reconciliation</h1>
          <p className="page-subtitle">
            Import bank activity, match settlement records and keep cash-to-ledger differences visible before close.
          </p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning">API not connected</StatusBadge>
          <button className="button button-primary" type="button" disabled>
            <UploadCloud size={15} aria-hidden="true" /> Import statement
          </button>
        </div>
      </header>

      <section className="connection-banner" aria-labelledby="banking-connection-title">
        <div className="connection-banner-copy">
          <Landmark size={19} aria-hidden="true" />
          <div>
            <strong id="banking-connection-title">Bank feeds stay guarded until the workspace connects</strong>
            <p>
              Imports will be tenant-scoped, duplicate-safe and immutable. Reconciliation will only link posted payments in the selected organization.
            </p>
          </div>
        </div>
        <Link className="button button-secondary" href="/settings#connections">Review connection</Link>
      </section>

      <section className="metric-grid" aria-label="Banking metrics">
        <DataCard label="Active bank accounts" value="—" meta="Count · live data required" icon={Landmark} />
        <DataCard label="Unmatched movements" value="—" meta="Count · import not connected" icon={CircleAlert} />
        <DataCard label="Reconciled this period" value="—" meta="THB · posted data required" icon={CheckCircle2} />
        <DataCard label="Difference to ledger" value="—" meta="THB · control not evaluated" status="Not evaluated" icon={SlidersHorizontal} />
      </section>

      <nav className="tab-list" aria-label="Banking sections">
        <a href="/banking" aria-current="page">Overview</a>
        <a href="/banking#accounts">Bank accounts</a>
        <a href="/banking#transactions">Transactions</a>
        <a href="/banking#reconciliation">Reconciliation queue</a>
      </nav>

      <section className="panel" id="accounts" aria-labelledby="bank-account-title">
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id="bank-account-title">Bank account register</h2>
              <p>Each account maps to one active asset ledger code and remains scoped to the current organization.</p>
            </div>
            <StatusBadge tone="info"><Landmark size={12} aria-hidden="true" /> Cash control</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar" aria-label="Bank account filters">
          <label className="search-trigger workbench-search" htmlFor="bank-account-search">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search bank accounts</span>
            <input id="bank-account-search" type="search" placeholder="Search account, bank or ledger code" disabled />
          </label>
          <button className="button button-secondary" type="button" disabled><Filter size={15} aria-hidden="true" /> Filters</button>
          <button className="button button-secondary" type="button" disabled><Landmark size={15} aria-hidden="true" /> Add account</button>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll bank account register horizontally">
          <table className="data-table">
            <caption>Bank account register</caption>
            <thead>
              <tr>
                <th scope="col">Account</th>
                <th scope="col">Bank</th>
                <th scope="col">Ledger mapping</th>
                <th scope="col">Currency</th>
                <th scope="col">Feed status</th>
                <th scope="col">Reconciliation</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="muted-cell" colSpan={6}>No bank accounts to display</td></tr>
            </tbody>
          </table>
        </div>
        <div className="empty-state workbench-empty">
          <span className="empty-state-icon" aria-hidden="true"><Landmark size={20} /></span>
          <strong>No connected bank accounts</strong>
          <p>Connect an authorized organization to map bank accounts, import statements and evaluate cash controls.</p>
          <StatusBadge tone="warning"><LockKeyhole size={12} aria-hidden="true" /> Import disabled</StatusBadge>
        </div>
      </section>

      <section className="panel-grid two-column" id="transactions">
        <div className="panel">
          <div className="section-heading">
            <div className="section-heading-row">
              <div>
                <h2 id="statement-intake-title">Statement intake</h2>
                <p>Every upload creates one traceable import batch before movements enter the queue.</p>
              </div>
              <StatusBadge tone="info"><FileCheck2 size={12} aria-hidden="true" /> Atomic import</StatusBadge>
            </div>
          </div>
          <div className="banking-control-list" aria-labelledby="statement-intake-title">
            {controls.map(({ label, detail, icon: Icon }) => (
              <div className="banking-control" key={label}>
                <span className="banking-control-icon" aria-hidden="true"><Icon size={16} /></span>
                <span><strong>{label}</strong><small>{detail}</small></span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel" id="reconciliation" aria-labelledby="reconciliation-queue-title">
          <div className="section-heading">
            <div className="section-heading-row">
              <div>
                <h2 id="reconciliation-queue-title">Reconciliation queue</h2>
                <p>Match statement movements to posted cash receipts and disbursements.</p>
              </div>
              <StatusBadge tone="warning"><CircleAlert size={12} aria-hidden="true" /> Not evaluated</StatusBadge>
            </div>
          </div>
          <div className="banking-queue-summary">
            <div><ArrowDownLeft size={16} aria-hidden="true" /><span><strong>Incoming</strong><small>Receipts to match</small></span><b>—</b></div>
            <div><ArrowUpRight size={16} aria-hidden="true" /><span><strong>Outgoing</strong><small>Disbursements to match</small></span><b>—</b></div>
          </div>
          <div className="empty-state banking-queue-empty">
            <span className="empty-state-icon" aria-hidden="true"><Link2 size={20} /></span>
            <strong>Reconciliation queue is empty</strong>
            <p>Connect a data source to load unmatched bank transactions and approved match candidates.</p>
          </div>
        </div>
      </section>

      <section className="panel" aria-labelledby="banking-workflow-title">
        <div className="section-heading">
          <h2 id="banking-workflow-title">Controlled cash lifecycle</h2>
          <p>Import, validation, matching and reconciliation are separated so operators can review evidence at every step.</p>
        </div>
        <ol className="workflow-rail">
          {workflow.map(({ label, detail, icon: Icon }, index) => (
            <li key={label} className={index === 0 ? "is-current" : undefined}>
              <span className="workflow-icon" aria-hidden="true"><Icon size={17} /></span>
              <span><strong>{label}</strong><small>{detail}</small></span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
