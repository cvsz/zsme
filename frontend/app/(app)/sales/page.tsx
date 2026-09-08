import { FileText, HandCoins, Plus, Receipt, Search, Users } from "lucide-react";

import { StatusBadge } from "@/components/design-system/status-badge";

export default function SalesPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Revenue operations</p>
          <h1 className="page-title">Sales & billing</h1>
          <p className="page-subtitle">Manage customers, invoices and collections from one governed operational surface.</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning">Awaiting tenant data</StatusBadge>
          <button className="button button-primary" type="button" disabled>
            <Plus size={15} aria-hidden="true" /> Create invoice
          </button>
        </div>
      </header>

      <section className="metric-grid" aria-label="Sales metrics">
        <article className="data-card"><div className="data-card-header"><span className="data-card-label">Open invoices</span><span className="data-card-icon" aria-hidden="true"><Receipt size={16} /></span></div><strong className="data-card-value">—</strong><div className="data-card-meta"><span>Count</span><StatusBadge tone="warning">No data</StatusBadge></div></article>
        <article className="data-card"><div className="data-card-header"><span className="data-card-label">Pipeline value</span><span className="data-card-icon" aria-hidden="true"><HandCoins size={16} /></span></div><strong className="data-card-value">—</strong><div className="data-card-meta"><span>THB</span><StatusBadge tone="warning">No data</StatusBadge></div></article>
        <article className="data-card"><div className="data-card-header"><span className="data-card-label">Customers</span><span className="data-card-icon" aria-hidden="true"><Users size={16} /></span></div><strong className="data-card-value">—</strong><div className="data-card-meta"><span>Active accounts</span><StatusBadge tone="warning">No data</StatusBadge></div></article>
        <article className="data-card"><div className="data-card-header"><span className="data-card-label">Collection health</span><span className="data-card-icon" aria-hidden="true"><FileText size={16} /></span></div><strong className="data-card-value">—</strong><div className="data-card-meta"><span>Policy checks</span><StatusBadge tone="warning">Not evaluated</StatusBadge></div></article>
      </section>

      <section className="panel" aria-labelledby="invoices-title">
        <div className="section-heading">
          <h2 id="invoices-title">Invoices</h2>
          <p>Customer and payment records will be loaded only after tenant authorization succeeds.</p>
        </div>
        <div className="page-actions">
          <button className="button button-secondary" type="button" disabled><Search size={15} aria-hidden="true" /> Search invoices</button>
          <StatusBadge tone="info">Tenant isolation enabled</StatusBadge>
        </div>
        <div className="empty-state">
          <span className="empty-state-icon" aria-hidden="true"><FileText size={20} /></span>
          <strong>No invoices to display</strong>
          <p>Connect the billing data source to view, issue and reconcile invoices.</p>
        </div>
      </section>
    </div>
  );
}
