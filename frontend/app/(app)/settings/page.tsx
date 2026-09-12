"use client";

import { Database, KeyRound, Save, ServerCog, ShieldCheck, UsersRound } from "lucide-react";
import { type FormEvent, useEffect, useState, useSyncExternalStore } from "react";

import { StatusBadge } from "@/components/design-system/status-badge";
import { useWorkspaceAccess } from "@/components/design-system/workspace-context";
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
import {
  listAccessRoles,
  listAccessUsers,
  replaceAccessUserRoles,
  type AccessRole,
  type AccessUser,
} from "@/lib/access";

type ConnectionState = "idle" | "managed" | "saved" | "checking" | "connected" | "unavailable" | "invalid";

export default function SettingsPage() {
  const { currentUser, hasPermission } = useWorkspaceAccess();
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [draftEndpoint, setDraftEndpoint] = useState<string | undefined>(undefined);
  const environmentManaged = isApiBaseUrlManaged();
  const endpointUserConfigurable = isApiEndpointUserConfigurable();
  const [connectionState, setConnectionState] = useState<ConnectionState>(environmentManaged ? "managed" : "idle");
  const [accessUsers, setAccessUsers] = useState<AccessUser[]>([]);
  const [accessRoles, setAccessRoles] = useState<AccessRole[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [accessLoading, setAccessLoading] = useState(false);
  const [accessSaving, setAccessSaving] = useState(false);
  const [accessError, setAccessError] = useState("");
  const endpoint = draftEndpoint ?? configuredEndpoint;
  const canReadAccess = Boolean(currentUser && hasPermission("organization:read"));
  const canWriteAccess = Boolean(currentUser && hasPermission("organization:write"));
  const manageableUsers = accessUsers.filter((user) => user.id !== currentUser?.user_id);

  useEffect(() => {
    if (!configuredEndpoint || !canReadAccess) {
      setAccessUsers([]);
      setAccessRoles([]);
      setSelectedUserId("");
      setSelectedRoleIds([]);
      return undefined;
    }

    const controller = new AbortController();
    setAccessLoading(true);
    setAccessError("");
    Promise.all([
      listAccessUsers(controller.signal),
      listAccessRoles(controller.signal),
    ])
      .then(([users, roles]) => {
        if (controller.signal.aborted) {
          return;
        }
        setAccessUsers(users);
        setAccessRoles(roles);
        const first = users.find((user) => user.id !== currentUser?.user_id);
        setSelectedUserId(first?.id || "");
        setSelectedRoleIds(first?.roles.map((role) => role.id) || []);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setAccessError("Access administration data is unavailable.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setAccessLoading(false);
        }
      });

    return () => controller.abort();
  }, [canReadAccess, configuredEndpoint, currentUser?.user_id]);

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

  const handleAccessUserChange = (userId: string) => {
    setSelectedUserId(userId);
    const user = accessUsers.find((item) => item.id === userId);
    setSelectedRoleIds(user?.roles.map((role) => role.id) || []);
    setAccessError("");
  };

  const handleRoleToggle = (roleId: string, checked: boolean) => {
    setSelectedRoleIds((current) => checked
      ? Array.from(new Set([...current, roleId]))
      : current.filter((id) => id !== roleId));
  };

  const handleSaveRoles = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedUserId || !canWriteAccess) {
      return;
    }
    setAccessSaving(true);
    setAccessError("");
    try {
      const updated = await replaceAccessUserRoles(selectedUserId, selectedRoleIds);
      setAccessUsers((current) => current.map((user) => user.id === updated.id ? updated : user));
      setSelectedRoleIds(updated.roles.map((role) => role.id));
    } catch {
      setAccessError("Role assignments could not be saved. Review your permissions and try again.");
    } finally {
      setAccessSaving(false);
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
            <p>Review organization users and manage tenant roles with server-side authorization and audit logging.</p>
          </div>
          {!currentUser ? (
            <div className="empty-state">
              <span className="empty-state-icon" aria-hidden="true"><UsersRound size={20} /></span>
              <strong>Sign in to manage access</strong>
              <p>Server-backed organization membership is required before making changes.</p>
            </div>
          ) : !canReadAccess ? (
            <p className="form-message" role="status">Your role does not include organization access administration.</p>
          ) : accessLoading ? (
            <p className="page-subtitle" role="status">Loading organization access…</p>
          ) : (
            <>
              <ul className="feature-list" aria-label="Organization users">
                {accessUsers.map((user) => (
                  <li key={user.id}>
                    <UsersRound size={16} aria-hidden="true" />
                    <span>
                      <strong>{user.display_name}</strong> · {user.email} · {user.roles.map((role) => role.name).join(", ") || "No roles"}
                      {user.id === currentUser.user_id ? " · Current operator" : ""}
                    </span>
                  </li>
                ))}
              </ul>
              {manageableUsers.length > 0 ? (
                <form className="form-grid" onSubmit={handleSaveRoles}>
                  <div className="field">
                    <label htmlFor="access-user">User to manage</label>
                    <select
                      id="access-user"
                      value={selectedUserId}
                      onChange={(event) => handleAccessUserChange(event.target.value)}
                    >
                      {manageableUsers.map((user) => (
                        <option key={user.id} value={user.id}>{user.display_name} · {user.email}</option>
                      ))}
                    </select>
                  </div>
                  <div className="form-grid" aria-label="Role assignments">
                    {accessRoles.map((role) => (
                      <label className="checkbox-field" key={role.id}>
                        <input
                          type="checkbox"
                          checked={selectedRoleIds.includes(role.id)}
                          disabled={!canWriteAccess || accessSaving}
                          onChange={(event) => handleRoleToggle(role.id, event.target.checked)}
                        />
                        <span>{role.name}<small>{role.permissions.join(", ") || "No permissions"}</small></span>
                      </label>
                    ))}
                  </div>
                  <div className="page-actions">
                    <button className="button button-primary" type="submit" disabled={!canWriteAccess || !selectedUserId || accessSaving}>
                      <Save size={15} aria-hidden="true" /> {accessSaving ? "Saving…" : "Save roles"}
                    </button>
                    {!canWriteAccess ? <StatusBadge tone="warning">Read only</StatusBadge> : <StatusBadge tone="success">Audited changes</StatusBadge>}
                  </div>
                </form>
              ) : (
                <p className="page-subtitle">No other organization users are available for role assignment.</p>
              )}
              {accessError ? <p className="form-message" role="alert">{accessError}</p> : null}
            </>
          )}
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
