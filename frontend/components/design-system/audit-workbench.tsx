import {
  CalendarClock,
  CheckCircle2,
  Download,
  FileClock,
  Filter,
  History,
  LockKeyhole,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";

const policies = [
  { label: "Append-only history", detail: "Material changes are retained as events instead of overwritten state.", icon: LockKeyhole },
  { label: "Tenant boundary", detail: "Queries are constrained to the authenticated tenant and organization context.", icon: ShieldCheck },
  { label: "Correlation lineage", detail: "Each event carries a correlation ID for request and workflow tracing.", icon: FileClock },
  { label: "Safe payloads", detail: "Credential-like fields are redacted before they reach an operator view.", icon: UserRoundCheck },
] as const;

export function AuditWorkbench() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Governance</p>
          <h1 className="page-title">Audit & activity</h1>
          <p className="page-subtitle">
            Review the evidence behind financial and administrative changes with scoped history, correlation lineage and safe payloads.
          </p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning">API not connected</StatusBadge>
          <button className="button button-secondary" type="button" disabled>
            <Download size={15} aria-hidden="true" /> Export audit log
          </button>
        </div>
      </header>

      <section className="connection-banner" aria-labelledby="audit-connection-title">
        <div className="connection-banner-copy">
          <ShieldCheck size={19} aria-hidden="true" />
          <div>
            <strong id="audit-connection-title">Audit evidence is unavailable until the workspace connects</strong>
            <p>Once connected, history will respect organization scope, permission policy and configured retention controls.</p>
          </div>
        </div>
        <Link className="button button-secondary" href="/settings#connections">Review connection</Link>
      </section>

      <section className="metric-grid" aria-label="Audit metrics">
        <DataCard label="Events this period" value="—" meta="Count · live data required" icon={History} />
        <DataCard label="Financial changes" value="—" meta="Count · policy scope required" icon={SlidersHorizontal} />
        <DataCard label="Active operators" value="—" meta="Count · identity data required" icon={UserRoundCheck} />
        <DataCard label="Redaction policy" value="Active" meta="Credentials excluded from views" status="Ready" icon={ShieldCheck} />
      </section>

      <nav className="tab-list" aria-label="Audit sections">
        <a href="/audit" aria-current="page">Event explorer</a>
        <a href="/audit#financial-controls">Financial controls</a>
        <a href="/audit#access-history">Access history</a>
      </nav>

      <section className="panel" aria-labelledby="audit-event-title">
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id="audit-event-title">Event explorer</h2>
              <p>Search actions, source entities and correlation IDs without changing the underlying audit record.</p>
            </div>
            <StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Append-only</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar" aria-label="Audit event filters">
          <label className="search-trigger workbench-search" htmlFor="audit-search">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search audit events</span>
            <input id="audit-search" type="search" placeholder="Search action, entity or correlation ID" disabled />
          </label>
          <button className="button button-secondary" type="button" disabled><Filter size={15} aria-hidden="true" /> Filters</button>
          <button className="button button-secondary" type="button" disabled><CalendarClock size={15} aria-hidden="true" /> Date range</button>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll audit events horizontally">
          <table className="data-table">
            <caption>Audit event explorer</caption>
            <thead>
              <tr>
                <th scope="col">Timestamp</th>
                <th scope="col">Action</th>
                <th scope="col">Entity</th>
                <th scope="col">Actor</th>
                <th scope="col">Correlation</th>
                <th scope="col">Payload</th>
              </tr>
            </thead>
            <tbody>
              <tr><td className="muted-cell" colSpan={6}>No audit events to display</td></tr>
            </tbody>
          </table>
        </div>
        <div className="empty-state workbench-empty">
          <span className="empty-state-icon" aria-hidden="true"><History size={20} /></span>
          <strong>No audit history to display</strong>
          <p>Connect an authorized organization to inspect immutable activity, financial posting lineage and access events.</p>
          <StatusBadge tone="warning"><LockKeyhole size={12} aria-hidden="true" /> Explorer disabled</StatusBadge>
        </div>
      </section>

      <section className="panel-grid two-column" id="financial-controls">
        <div className="panel">
          <div className="section-heading">
            <h2>Evidence contract</h2>
            <p>Audit data is designed as a control surface, not a generic activity feed.</p>
          </div>
          <div className="audit-policy-list">
            {policies.map(({ label, detail, icon: Icon }) => (
              <div className="audit-policy" key={label}>
                <span className="audit-policy-icon" aria-hidden="true"><Icon size={16} /></span>
                <span><strong>{label}</strong><small>{detail}</small></span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel" id="access-history" aria-labelledby="audit-review-title">
          <div className="section-heading">
            <div className="section-heading-row">
              <div>
                <h2 id="audit-review-title">Review posture</h2>
                <p>Use event history to support close, incident response and administrator review.</p>
              </div>
              <StatusBadge tone="success"><CheckCircle2 size={12} aria-hidden="true" /> Policy ready</StatusBadge>
            </div>
          </div>
          <ul className="feature-list">
            <li><CheckCircle2 size={16} aria-hidden="true" />Financial actions retain source and actor context.</li>
            <li><CheckCircle2 size={16} aria-hidden="true" />Filter and pagination are deterministic for repeatable review.</li>
            <li><CheckCircle2 size={16} aria-hidden="true" />Exports remain permission-aware and connection-gated.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
