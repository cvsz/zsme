import {
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle2,
  CircleDollarSign,
  FileCheck2,
  FilePlus2,
  Filter,
  Link2,
  LockKeyhole,
  ReceiptText,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";

type PaymentKind = "receipt" | "disbursement";

const copy = {
  receipt: {
    eyebrow: "Accounts receivable",
    title: "Customer receipts",
    subtitle: "Record incoming cash, allocate it to one or more posted invoices and keep residual advances explicit.",
    action: "Record receipt",
    partner: "customer",
    plural: "receipts",
    control: "Cash in",
    icon: ArrowDownLeft,
    empty: "No receipts to display",
  },
  disbursement: {
    eyebrow: "Accounts payable",
    title: "Vendor disbursements",
    subtitle: "Record outgoing cash, settle supplier bills and preserve payment evidence through an auditable ledger trail.",
    action: "Record disbursement",
    partner: "vendor",
    plural: "disbursements",
    control: "Cash out",
    icon: ArrowUpRight,
    empty: "No disbursements to display",
  },
} as const;

const controls = [
  { label: "Draft", description: "Capture amount and allocation", icon: ReceiptText },
  { label: "Review", description: "Confirm partner and residual", icon: ShieldCheck },
  { label: "Post", description: "Create balanced journal entry", icon: FileCheck2 },
  { label: "Reconcile", description: "Trace cash to statement", icon: CheckCircle2 },
] as const;

export function PaymentWorkbench({ kind }: Readonly<{ kind: PaymentKind }>) {
  const page = copy[kind];
  const Icon = page.icon;

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">{page.eyebrow}</p>
          <h1 className="page-title">{page.title}</h1>
          <p className="page-subtitle">{page.subtitle}</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning">API not connected</StatusBadge>
          <button className="button button-primary" type="button" disabled>
            <FilePlus2 size={15} aria-hidden="true" /> {page.action}
          </button>
        </div>
      </header>

      <section className="connection-banner" aria-labelledby={`${kind}-connection-title`}>
        <div className="connection-banner-copy">
          <Link2 size={19} aria-hidden="true" />
          <div>
            <strong id={`${kind}-connection-title`}>Cash movements stay guarded until the workspace connects</strong>
            <p>Allocations will be checked against posted documents, open balances and the current organization&apos;s permissions.</p>
          </div>
        </div>
        <Link className="button button-secondary" href="/settings#connections">Review connection</Link>
      </section>

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        <DataCard label={`Open ${page.plural}`} value="—" meta="Count · live data required" icon={ReceiptText} />
        <DataCard label="Allocated this period" value="—" meta="THB · posted data required" icon={CircleDollarSign} />
        <DataCard label="Unapplied balance" value="—" meta="THB · control not evaluated" icon={Icon} />
        <DataCard label="Reconciliation health" value="—" meta="Policy checks" status="Not evaluated" icon={LockKeyhole} />
      </section>

      <nav className="tab-list" aria-label={`${page.title} sections`}>
        <a href={`/${page.plural}`} aria-current="page">All {page.plural}</a>
        <a href={`/${page.plural}?status=draft`}>Draft</a>
        <a href={`/${page.plural}?status=posted`}>Posted</a>
        <a href={`/${page.plural}?status=unapplied`}>Unapplied</a>
      </nav>

      <section className="panel" aria-labelledby={`${kind}-register-title`}>
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id={`${kind}-register-title`}>{page.title} register</h2>
              <p>Each movement will retain partner, allocation, cash-account and ledger references.</p>
            </div>
            <StatusBadge tone="info"><Icon size={12} aria-hidden="true" /> {page.control}</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar">
          <label className="search-trigger workbench-search" htmlFor={`${kind}-search`}>
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search {page.plural}</span>
            <input id={`${kind}-search`} type="search" placeholder={`Search by number or ${page.partner}`} disabled />
          </label>
          <button className="button button-secondary" type="button" disabled><Filter size={15} aria-hidden="true" /> Filters</button>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label={`Scroll ${page.plural} register horizontally`}>
          <table className="data-table">
            <caption>{page.title} register</caption>
            <thead>
              <tr>
                <th scope="col">Payment</th>
                <th scope="col">{page.partner}</th>
                <th scope="col">Date</th>
                <th scope="col">Amount</th>
                <th scope="col">Allocation</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody><tr><td className="muted-cell" colSpan={6}>{page.empty}</td></tr></tbody>
          </table>
        </div>
        <div className="empty-state workbench-empty">
          <span className="empty-state-icon" aria-hidden="true"><Icon size={20} /></span>
          <strong>{page.empty}</strong>
          <p>Connect an authorized organization to create, allocate and post {page.plural}.</p>
          <StatusBadge tone="warning"><LockKeyhole size={12} aria-hidden="true" /> Posting disabled</StatusBadge>
        </div>
      </section>

      <section className="panel" aria-labelledby={`${kind}-controls-title`}>
        <div className="section-heading">
          <h2 id={`${kind}-controls-title`}>Settlement controls</h2>
          <p>Balances remain reproducible from immutable documents, payment allocations and posted ledger lines.</p>
        </div>
        <ol className="workflow-rail">
          {controls.map(({ label, description, icon: ControlIcon }, index) => (
            <li key={label} className={index === 0 ? "is-current" : undefined}>
              <span className="workflow-icon" aria-hidden="true"><ControlIcon size={17} /></span>
              <span><strong>{label}</strong><small>{description}</small></span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
