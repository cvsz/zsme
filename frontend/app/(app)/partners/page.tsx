import { Building2, ContactRound, FilePlus2, Search, ShieldCheck, Tags } from "lucide-react";

import { StatusBadge } from "@/components/design-system/status-badge";

export default function PartnersPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Partner master</p>
          <h1 className="page-title">Customers & vendors</h1>
          <p className="page-subtitle">Keep customer, supplier and business-partner identity consistent across sales, purchasing and the ledger.</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning">Awaiting tenant data</StatusBadge>
          <button className="button button-primary" type="button" disabled>
            <FilePlus2 size={15} aria-hidden="true" /> Add partner
          </button>
        </div>
      </header>

      <nav className="tab-list" aria-label="Partner sections">
        <a href="/partners" aria-current="page">All partners</a>
        <a href="/partners?type=customer">Customers</a>
        <a href="/partners?type=vendor">Vendors</a>
        <a href="/partners?archived=true">Archived</a>
      </nav>

      <section className="panel" aria-labelledby="directory-title">
        <div className="section-heading">
          <h2 id="directory-title">Partner directory</h2>
          <p>Tax identity, payment terms and addresses are held at the organization boundary.</p>
        </div>
        <div className="page-actions">
          <label className="search-trigger" htmlFor="partner-search">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search partners</span>
            <input id="partner-search" type="search" placeholder="Search by code, name or tax ID" disabled />
          </label>
          <StatusBadge tone="info"><ShieldCheck size={12} aria-hidden="true" /> Tenant scoped</StatusBadge>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll partner directory table horizontally">
          <table className="data-table">
            <caption>Customer and vendor directory</caption>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Partner</th>
                <th scope="col">Type</th>
                <th scope="col">Payment terms</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="muted-cell" colSpan={5}>No connected partners</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <div className="panel-grid two-column">
        <section className="panel" aria-labelledby="identity-title">
          <div className="section-heading">
            <h2 id="identity-title">Identity contract</h2>
            <p>Partner records are designed for Thai SME workflows.</p>
          </div>
          <ul className="feature-list">
            <li><ContactRound size={16} aria-hidden="true" /> Customer, vendor or both classifications.</li>
            <li><Building2 size={16} aria-hidden="true" /> Legal name, tax ID and establishment branch.</li>
            <li><Tags size={16} aria-hidden="true" /> Tags and payment terms for operational filtering.</li>
          </ul>
        </section>
        <section className="panel" aria-labelledby="governance-title">
          <div className="section-heading">
            <h2 id="governance-title">Change governance</h2>
            <p>Edits use optimistic versions and append-only audit events.</p>
          </div>
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true"><ShieldCheck size={20} /></span>
            <strong>Partner actions are guarded</strong>
            <p>Connect an organization before creating, editing or archiving a partner record.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
