import {
  BarChart3,
  FileBarChart,
  FileCheck2,
  FileSpreadsheet,
  Landmark,
  LockKeyhole,
  PieChart,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/design-system/status-badge";

const reports = [
  { href: "/reports/trial-balance", label: "Trial balance", description: "Verify total debits and credits by account.", icon: FileSpreadsheet },
  { href: "/reports/profit-loss", label: "Profit & loss", description: "Understand revenue, expenses and operating result.", icon: BarChart3 },
  { href: "/reports/balance-sheet", label: "Balance sheet", description: "Review assets, liabilities and equity position.", icon: PieChart },
  { href: "/reports/general-ledger", label: "General ledger", description: "Drill from account totals to immutable entries.", icon: FileBarChart },
  { href: "/reports/aged-receivable", label: "Aged receivable", description: "Track outstanding customer balances and ageing.", icon: Landmark },
  { href: "/reports/aged-payable", label: "Aged payable", description: "Track supplier obligations and due dates.", icon: FileCheck2 },
] as const;

export function ReportCenter({ activeReport }: Readonly<{ activeReport?: string }>) {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Financial intelligence</p>
          <h1 className="page-title">Reports & insights</h1>
          <p className="page-subtitle">Ledger-derived reporting with clear date scope, source lineage and export-ready contracts.</p>
        </div>
        <div className="page-actions"><StatusBadge tone="warning">API not connected</StatusBadge></div>
      </header>

      <section className="connection-banner" aria-labelledby="reports-connection-title">
        <div className="connection-banner-copy">
          <ShieldCheck size={19} aria-hidden="true" />
          <div>
            <strong id="reports-connection-title">Reports never invent a balance</strong>
            <p>Once connected, totals will be derived from posted, tenant-scoped ledger lines and remain drillable to source records.</p>
          </div>
        </div>
        <Link className="button button-secondary" href="/settings#connections">Review connection</Link>
      </section>

      <section className="report-grid" aria-label="Available financial reports">
        {reports.map(({ href, label, description, icon: Icon }) => (
          <Link className={`report-card${activeReport === label ? " is-active" : ""}`} href={href} key={href}>
            <span className="report-card-icon" aria-hidden="true"><Icon size={19} /></span>
            <span><strong>{label}</strong><small>{description}</small></span>
            <StatusBadge tone="warning">Not connected</StatusBadge>
          </Link>
        ))}
      </section>

      <section className="panel" aria-labelledby="report-preview-title">
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id="report-preview-title">Report preview</h2>
              <p>Choose a report above, then set date, organization and account filters when the API is ready.</p>
            </div>
            <StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Posted ledger only</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar">
          <label className="search-trigger workbench-search" htmlFor="report-search">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search report accounts</span>
            <input id="report-search" type="search" placeholder="Filter by account or source" disabled />
          </label>
          <button className="button button-secondary" type="button" disabled>From 01 Jan 2026</button>
          <button className="button button-secondary" type="button" disabled>To 31 Dec 2026</button>
        </div>
        <div className="empty-state">
          <span className="empty-state-icon" aria-hidden="true"><FileSpreadsheet size={20} /></span>
          <strong>No report data to display</strong>
          <p>Connect a tenant data source to generate a report from immutable, posted accounting activity.</p>
        </div>
      </section>
    </div>
  );
}
