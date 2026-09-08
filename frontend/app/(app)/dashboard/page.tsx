import {
  Banknote,
  BarChart3,
  FileCheck2,
  Landmark,
  Link2,
  RefreshCw,
  ShieldCheck,
  WalletCards,
} from "lucide-react";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";

export default function DashboardPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Command center</p>
          <h1 className="page-title">Business control center</h1>
          <p className="page-subtitle">
            A calm, auditable view of your business operations. Connect a tenant data source to activate live insight.
          </p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="info">Design system v1</StatusBadge>
          <button className="button button-secondary" type="button" disabled>
            <RefreshCw size={15} aria-hidden="true" />
            Refresh data
          </button>
        </div>
      </header>

      <section className="connection-banner" aria-labelledby="connection-title">
        <div className="connection-banner-copy">
          <Link2 size={19} aria-hidden="true" />
          <div>
            <strong id="connection-title">Data source not configured</strong>
            <p>Connect the ZSME API and a tenant workspace to activate financial totals, workflows and live reporting.</p>
          </div>
        </div>
        <a className="button button-primary" href="/settings#connections">Review connection settings</a>
      </section>

      <section className="metric-grid" aria-label="Key business metrics">
        <DataCard label="Cash position" value="—" meta="THB · current balance" icon={WalletCards} />
        <DataCard label="Receivables" value="—" meta="THB · outstanding" icon={Banknote} />
        <DataCard label="Payables" value="—" meta="THB · outstanding" icon={Landmark} />
        <DataCard label="Control health" value="—" meta="Policy checks" status="Not evaluated" icon={ShieldCheck} />
      </section>

      <div className="panel-grid two-column">
        <section className="panel" aria-labelledby="activity-title">
          <div className="section-heading">
            <h2 id="activity-title">Recent activity</h2>
            <p>Immutable journal and operational events will appear here after connection.</p>
          </div>
          <div className="data-table-wrap" tabIndex={0} aria-label="Scroll recent activity table horizontally">
            <table className="data-table">
              <caption>Recent accounting and operational activity</caption>
              <thead>
                <tr>
                  <th scope="col">Event</th>
                  <th scope="col">Owner</th>
                  <th scope="col">Status</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="muted-cell" colSpan={4}>No connected events</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel" aria-labelledby="readiness-title">
          <div className="section-heading">
            <h2 id="readiness-title">Readiness controls</h2>
            <p>Enterprise guardrails remain visible before data is live.</p>
          </div>
          <ul className="feature-list">
            <li><FileCheck2 size={16} aria-hidden="true" /> Double-entry validation at the ledger boundary.</li>
            <li><ShieldCheck size={16} aria-hidden="true" /> Tenant-scoped authorization and audit events.</li>
            <li><BarChart3 size={16} aria-hidden="true" /> Report-ready data contracts with truthful empty states.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
