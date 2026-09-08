import { BookOpen, CalendarClock, FilePlus2, LockKeyhole, Search } from "lucide-react";

import { StatusBadge } from "@/components/design-system/status-badge";

export default function AccountingPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Core ledger</p>
          <h1 className="page-title">Accounting workspace</h1>
          <p className="page-subtitle">Post, review and reconcile double-entry activity with clear period and approval controls.</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning">API connection required</StatusBadge>
          <button className="button button-primary" type="button" disabled>
            <FilePlus2 size={15} aria-hidden="true" /> New journal entry
          </button>
        </div>
      </header>

      <nav className="tab-list" aria-label="Accounting sections">
        <a href="/accounting" aria-current="page">Journal</a>
        <a href="/accounting/chart-of-accounts">Chart of accounts</a>
        <a href="/accounting/periods">Fiscal periods</a>
        <a href="/accounting/reconciliation">Reconciliation</a>
      </nav>

      <section className="panel" aria-labelledby="ledger-title">
        <div className="section-heading">
          <h2 id="ledger-title">Journal entries</h2>
          <p>Every posted entry will be balanced, tenant-scoped, idempotent and immutable.</p>
        </div>
        <div className="page-actions">
          <button className="button button-secondary" type="button" disabled>
            <Search size={15} aria-hidden="true" /> Filter entries
          </button>
          <button className="button button-secondary" type="button" disabled>
            <CalendarClock size={15} aria-hidden="true" /> Fiscal year 2026
          </button>
        </div>
        <div className="empty-state">
          <span className="empty-state-icon" aria-hidden="true"><BookOpen size={20} /></span>
          <strong>Ledger is ready for a connected workspace</strong>
          <p>Configure an API connection and organization before creating or importing accounting activity.</p>
          <StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Posting is guarded</StatusBadge>
        </div>
      </section>
    </div>
  );
}
