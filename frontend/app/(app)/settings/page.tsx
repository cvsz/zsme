import { Database, KeyRound, Save, ServerCog, ShieldCheck, UsersRound } from "lucide-react";

import { StatusBadge } from "@/components/design-system/status-badge";

export default function SettingsPage() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Control plane</p>
          <h1 className="page-title">Workspace settings</h1>
          <p className="page-subtitle">Configure the operating boundary for tenants, people, connections and governance.</p>
        </div>
        <div className="page-actions"><StatusBadge tone="info">Admin surface</StatusBadge></div>
      </header>

      <section className="panel" id="connections" aria-labelledby="connection-settings-title">
        <div className="section-heading">
          <h2 id="connection-settings-title">API connection</h2>
          <p>Secrets belong in managed deployment configuration. They are never stored in the browser UI.</p>
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="api-endpoint">API endpoint</label>
            <input id="api-endpoint" name="api-endpoint" type="url" placeholder="https://api.example.com" disabled />
            <small>Use an HTTPS endpoint for production traffic.</small>
          </div>
          <div className="field">
            <label htmlFor="workspace-slug">Workspace slug</label>
            <input id="workspace-slug" name="workspace-slug" type="text" placeholder="your-tenant" disabled />
            <small>Tenant selection is resolved by server-side authorization.</small>
          </div>
          <div className="page-actions">
            <button className="button button-primary" type="button" disabled><Save size={15} aria-hidden="true" /> Save connection</button>
            <StatusBadge tone="warning">Not configured</StatusBadge>
          </div>
        </div>
      </section>

      <div className="panel-grid two-column">
        <section className="panel" aria-labelledby="governance-title">
          <div className="section-heading">
            <h2 id="governance-title">Governance posture</h2>
            <p>Controls that protect financial data and operator actions.</p>
          </div>
          <ul className="feature-list">
            <li><ShieldCheck size={16} aria-hidden="true" /> Role-based permissions are evaluated server-side.</li>
            <li><KeyRound size={16} aria-hidden="true" /> Access tokens are opaque and revocable.</li>
            <li><Database size={16} aria-hidden="true" /> Journal records are append-only after posting.</li>
          </ul>
        </section>
        <section className="panel" aria-labelledby="access-title">
          <div className="section-heading">
            <h2 id="access-title">Access administration</h2>
            <p>People and role assignments will be managed here.</p>
          </div>
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true"><UsersRound size={20} /></span>
            <strong>Connect a tenant to manage access</strong>
            <p>Server-backed organization membership is required before making changes.</p>
          </div>
        </section>
      </div>

      <section className="panel" aria-labelledby="environment-title">
        <div className="section-heading">
          <h2 id="environment-title">Environment status</h2>
          <p>Operational information is intentionally separated from customer data.</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone="warning"><ServerCog size={12} aria-hidden="true" /> API not connected</StatusBadge>
          <span className="page-subtitle">Release controls require an authenticated operator and deployment policy.</span>
        </div>
      </section>
    </div>
  );
}
