"use client";

import { Database, KeyRound, Save, ServerCog, ShieldCheck, UsersRound } from "lucide-react";
import { type FormEvent, useState, useSyncExternalStore } from "react";

import { StatusBadge } from "@/components/design-system/status-badge";
import {
  ApiConfigurationError,
  checkApiHealth,
  getApiBaseUrl,
  getServerApiBaseUrl,
  isApiEndpointUserConfigurable,
  isApiBaseUrlManaged,
  setApiBaseUrl,
  subscribeToApiBaseUrl,
} from "@/lib/api-client";

type ConnectionState = "idle" | "managed" | "saved" | "checking" | "connected" | "unavailable" | "invalid";

export default function SettingsPage() {
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [draftEndpoint, setDraftEndpoint] = useState<string | undefined>(undefined);
  const environmentManaged = isApiBaseUrlManaged();
  const endpointUserConfigurable = isApiEndpointUserConfigurable();
  const [connectionState, setConnectionState] = useState<ConnectionState>(environmentManaged ? "managed" : "idle");
  const endpoint = draftEndpoint ?? configuredEndpoint;

  const handleSaveConnection = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (environmentManaged) {
      setConnectionState("managed");
      return;
    }
    try {
      setDraftEndpoint(setApiBaseUrl(endpoint));
      setConnectionState(endpoint.trim() ? "saved" : "idle");
    } catch (error) {
      setConnectionState(error instanceof ApiConfigurationError ? "invalid" : "unavailable");
    }
  };

  const handleTestConnection = async () => {
    setConnectionState("checking");
    try {
      await checkApiHealth();
      setConnectionState("connected");
    } catch {
      setConnectionState("unavailable");
    }
  };

  const connectionLabel = {
    idle: "Not configured",
    managed: "Managed by deployment",
    saved: "Saved locally",
    checking: "Checking…",
    connected: "Connected",
    unavailable: "Unavailable",
    invalid: "Invalid endpoint",
  }[connectionState];
  const connectionTone = connectionState === "connected" ? "success" : connectionState === "invalid" || connectionState === "unavailable" ? "danger" : connectionState === "managed" ? "info" : "warning";

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
        <form className="form-grid" onSubmit={handleSaveConnection}>
          <div className="field">
            <label htmlFor="api-endpoint">API endpoint</label>
            <input id="api-endpoint" name="api-endpoint" type="url" value={endpoint} onChange={(event) => setDraftEndpoint(event.target.value)} placeholder="https://api.example.com" readOnly={!endpointUserConfigurable} />
            <small>{endpointUserConfigurable ? "Use an HTTPS endpoint for production traffic." : "This endpoint is supplied by the deployment environment; browser overrides are disabled."}</small>
          </div>
          <div className="field">
            <label htmlFor="workspace-slug">Workspace slug</label>
            <input id="workspace-slug" name="workspace-slug" type="text" placeholder="your-tenant" disabled />
            <small>Tenant selection is resolved by server-side authorization.</small>
          </div>
          <div className="page-actions">
            <button className="button button-primary" type="submit" disabled={!endpointUserConfigurable}><Save size={15} aria-hidden="true" /> Save connection</button>
            <button className="button button-secondary" type="button" onClick={handleTestConnection} disabled={!endpoint.trim() || connectionState === "checking"}><ServerCog size={15} aria-hidden="true" /> Test connection</button>
            <StatusBadge tone={connectionTone}>{connectionLabel}</StatusBadge>
          </div>
        </form>
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
        <section className="panel" id="access" aria-labelledby="access-title">
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
          <StatusBadge tone={connectionTone}><ServerCog size={12} aria-hidden="true" /> API {connectionLabel}</StatusBadge>
          <span className="page-subtitle">Release controls require an authenticated operator and deployment policy.</span>
        </div>
      </section>
    </div>
  );
}
