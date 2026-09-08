import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  FilePlus2,
  FileText,
  Filter,
  Link2,
  LockKeyhole,
  Search,
  Send,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";

type DocumentKind = "invoice" | "bill";

const copy = {
  invoice: {
    eyebrow: "Accounts receivable",
    title: "Sales invoices",
    subtitle: "Issue customer invoices, post revenue and keep every receivable traceable to an auditable ledger entry.",
    singular: "invoice",
    plural: "invoices",
    partner: "customer",
    control: "Accounts receivable",
    action: "Create invoice",
    empty: "No invoices to display",
    emptyDescription: "Connect an authorized organization to load, issue and post customer invoices.",
    directionIcon: ArrowUpFromLine,
    accentIcon: CircleDollarSign,
  },
  bill: {
    eyebrow: "Accounts payable",
    title: "Vendor bills",
    subtitle: "Capture supplier bills, route them through review and post payable obligations with tax-aware double-entry controls.",
    singular: "bill",
    plural: "bills",
    partner: "vendor",
    control: "Accounts payable",
    action: "Create bill",
    empty: "No bills to display",
    emptyDescription: "Connect an authorized organization to load, capture and post vendor bills.",
    directionIcon: ArrowDownToLine,
    accentIcon: FileText,
  },
} as const;

const workflow = [
  { label: "Draft", detail: "Prepare line items and tax details", icon: FileText },
  { label: "Review", detail: "Validate partner, accounts and approvals", icon: ShieldCheck },
  { label: "Post to ledger", detail: "Create one balanced immutable entry", icon: Send },
  { label: "Reconcile", detail: "Track settlement against the document", icon: CheckCircle2 },
] as const;

export function DocumentWorkbench({ kind }: Readonly<{ kind: DocumentKind }>) {
  const page = copy[kind];
  const DirectionIcon = page.directionIcon;
  const AccentIcon = page.accentIcon;

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
            <strong id={`${kind}-connection-title`}>Live {page.plural} are guarded until the workspace connects</strong>
            <p>Data access, document creation and ledger posting will use the signed-in tenant&apos;s organization boundary.</p>
          </div>
        </div>
        <Link className="button button-secondary" href="/settings#connections">
          Review connection
        </Link>
      </section>

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        <DataCard label={`Open ${page.plural}`} value="—" meta="Count · live data required" icon={page.directionIcon} />
        <DataCard label="Awaiting review" value="—" meta="Count · workflow not connected" icon={ShieldCheck} />
        <DataCard label="Posted this period" value="—" meta="THB · ledger data required" icon={AccentIcon} />
        <DataCard label="Control health" value="—" meta="Policy checks" status="Not evaluated" icon={LockKeyhole} />
      </section>

      <nav className="tab-list" aria-label={`${page.title} sections`}>
        <a href={`/${page.plural}`} aria-current="page">All {page.plural}</a>
        <a href={`/${page.plural}?status=draft`}>Draft</a>
        <a href={`/${page.plural}?status=posted`}>Posted</a>
        <a href={`/${page.plural}?status=overdue`}>Needs attention</a>
      </nav>

      <section className="panel" aria-labelledby={`${kind}-directory-title`}>
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id={`${kind}-directory-title`}>{page.title} register</h2>
              <p>Every document will carry a unique number, fixed-precision totals and a verifiable posting lineage.</p>
            </div>
            <StatusBadge tone="info"><DirectionIcon size={12} aria-hidden="true" /> {page.control}</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar" aria-label={`${page.title} filters`}>
          <label className="search-trigger workbench-search" htmlFor={`${kind}-search`}>
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search {page.plural}</span>
            <input id={`${kind}-search`} type="search" placeholder={`Search by number or ${page.partner}`} disabled />
          </label>
          <button className="button button-secondary" type="button" disabled>
            <Filter size={15} aria-hidden="true" /> Filters
          </button>
          <button className="button button-secondary" type="button" disabled>
            <CalendarClock size={15} aria-hidden="true" /> Fiscal year 2026
          </button>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label={`Scroll ${page.plural} register table horizontally`}>
          <table className="data-table">
            <caption>{page.title} register</caption>
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">{page.partner}</th>
                <th scope="col">Issue date</th>
                <th scope="col">Total</th>
                <th scope="col">Status</th>
                <th scope="col">Ledger</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="muted-cell" colSpan={6}>{page.empty}</td></tr>
            </tbody>
          </table>
        </div>
        <div className="empty-state workbench-empty">
          <span className="empty-state-icon" aria-hidden="true"><FileText size={20} /></span>
          <strong>{page.empty}</strong>
          <p>{page.emptyDescription}</p>
          <StatusBadge tone="warning"><LockKeyhole size={12} aria-hidden="true" /> Creation and posting disabled</StatusBadge>
        </div>
      </section>

      <section className="panel" aria-labelledby={`${kind}-workflow-title`}>
        <div className="section-heading">
          <h2 id={`${kind}-workflow-title`}>Controlled document lifecycle</h2>
          <p>Workflow visibility stays available even when live tenant data is unavailable.</p>
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
