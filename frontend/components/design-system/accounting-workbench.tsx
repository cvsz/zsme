import {
  BookOpenCheck,
  CalendarCheck2,
  CircleHelp,
  FileClock,
  Landmark,
  LockKeyhole,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";

type AccountingSurface = "accounts" | "periods" | "reconciliation";

const content = {
  accounts: {
    eyebrow: "Accounting master data",
    title: "Chart of accounts",
    subtitle: "Manage a structured account hierarchy with clear posting boundaries and an audit-safe change history.",
    tab: "Chart of accounts",
    icon: BookOpenCheck,
    emptyTitle: "Chart of accounts is waiting for an organization",
    emptyDescription: "Connect an authorized organization to load, create and govern postable account codes.",
  },
  periods: {
    eyebrow: "Close management",
    title: "Fiscal periods",
    subtitle: "Open, review and lock accounting periods with explicit close controls and immutable posting boundaries.",
    tab: "Fiscal periods",
    icon: CalendarCheck2,
    emptyTitle: "No fiscal periods connected",
    emptyDescription: "Connect an organization to review period status and execute an authorized close workflow.",
  },
  reconciliation: {
    eyebrow: "Cash controls",
    title: "Reconciliation workspace",
    subtitle: "Prepare bank and cash reconciliation with evidence-led matching and no silent ledger changes.",
    tab: "Reconciliation",
    icon: Landmark,
    emptyTitle: "Reconciliation is not connected",
    emptyDescription: "Connect a bank statement source to import transactions, review candidates and reconcile safely.",
  },
} as const;

export function AccountingWorkbench({ surface }: Readonly<{ surface: AccountingSurface }>) {
  const page = content[surface];
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
            <Plus size={15} aria-hidden="true" /> {surface === "accounts" ? "Add account" : surface === "periods" ? "Open period" : "Import statement"}
          </button>
        </div>
      </header>

      <nav className="tab-list" aria-label="Accounting administration sections">
        <Link href="/accounting">Journal</Link>
        <Link href="/accounting/chart-of-accounts" aria-current={surface === "accounts" ? "page" : undefined}>Chart of accounts</Link>
        <Link href="/accounting/periods" aria-current={surface === "periods" ? "page" : undefined}>Fiscal periods</Link>
        <Link href="/accounting/reconciliation" aria-current={surface === "reconciliation" ? "page" : undefined}>Reconciliation</Link>
      </nav>

      <section className="connection-banner" aria-labelledby={`${surface}-connection-title`}>
        <div className="connection-banner-copy">
          <ShieldCheck size={19} aria-hidden="true" />
          <div>
            <strong id={`${surface}-connection-title`}>Controls are visible before live data is enabled</strong>
            <p>Every action will be scoped to the signed-in organization and append a verifiable audit event.</p>
          </div>
        </div>
        <Link className="button button-secondary" href="/settings#connections">Review connection</Link>
      </section>

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        <DataCard label={surface === "accounts" ? "Active accounts" : surface === "periods" ? "Open periods" : "Unmatched items"} value="—" meta="Live data required" icon={Icon} />
        <DataCard label={surface === "accounts" ? "Control accounts" : surface === "periods" ? "Locked periods" : "Suggested matches"} value="—" meta="Not evaluated" icon={ShieldCheck} />
        <DataCard label="Last activity" value="—" meta="Audit timestamp" icon={FileClock} />
        <DataCard label="Control health" value="—" meta="Policy checks" status="Not evaluated" icon={LockKeyhole} />
      </section>

      <section className="panel" aria-labelledby={`${surface}-register-title`}>
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id={`${surface}-register-title`}>{page.tab} register</h2>
              <p>Live records will appear only after tenant authorization and API readiness are confirmed.</p>
            </div>
            <StatusBadge tone="info"><ShieldCheck size={12} aria-hidden="true" /> Tenant scoped</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar">
          <label className="search-trigger workbench-search" htmlFor={`${surface}-search`}>
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search {page.tab}</span>
            <input id={`${surface}-search`} type="search" placeholder={`Search ${page.tab.toLowerCase()}`} disabled />
          </label>
          <button className="button button-secondary" type="button" disabled><RefreshCw size={15} aria-hidden="true" /> Refresh</button>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label={`Scroll ${page.tab} table horizontally`}>
          <table className="data-table">
            <caption>{page.tab} register</caption>
            <thead>
              <tr>
                <th scope="col">Code / period</th>
                <th scope="col">Name / date range</th>
                <th scope="col">Status</th>
                <th scope="col">Version</th>
                <th scope="col">Controls</th>
              </tr>
            </thead>
            <tbody><tr><td className="muted-cell" colSpan={5}>No connected records</td></tr></tbody>
          </table>
        </div>
        <div className="empty-state workbench-empty">
          <span className="empty-state-icon" aria-hidden="true"><Icon size={20} /></span>
          <strong>{page.emptyTitle}</strong>
          <p>{page.emptyDescription}</p>
          <StatusBadge tone="warning"><CircleHelp size={12} aria-hidden="true" /> Actions remain guarded</StatusBadge>
        </div>
      </section>
    </div>
  );
}
