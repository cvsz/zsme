"use client";

import {
  CalendarClock,
  CheckCircle2,
  Download,
  FileClock,
  Filter,
  History,
  LockKeyhole,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UserRoundCheck,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState, useSyncExternalStore } from "react";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";
import {
  ApiConfigurationError,
  ApiError,
  getAccessToken,
  getApiBaseUrl,
  getServerApiBaseUrl,
  subscribeToApiBaseUrl,
} from "@/lib/api-client";
import { exportAuditEvents, listAuditEvents, type AuditEvent } from "@/lib/audit";

const policies = [
  { label: "Append-only history", detail: "Material changes are retained as events instead of overwritten state.", icon: LockKeyhole },
  { label: "Tenant boundary", detail: "Queries are constrained to the authenticated tenant and organization context.", icon: ShieldCheck },
  { label: "Correlation lineage", detail: "Each event carries a correlation ID for request and workflow tracing.", icon: FileClock },
  { label: "Safe payloads", detail: "Credential-like fields are redacted before they reach an operator view.", icon: UserRoundCheck },
] as const;

type LoadState = "idle" | "ready" | "error";
type Filters = { action: string; entityType: string };

function readInitialFilters(): Filters {
  if (typeof window === "undefined") {
    return { action: "", entityType: "" };
  }
  const params = new URLSearchParams(window.location.search);
  return { action: params.get("action") || "", entityType: params.get("entity_type") || "" };
}

function updateLocation(filters: Filters): void {
  const params = new URLSearchParams();
  if (filters.action) {
    params.set("action", filters.action);
  }
  if (filters.entityType) {
    params.set("entity_type", filters.entityType);
  }
  const query = params.toString();
  window.history.replaceState(null, "", `/audit${query ? `?${query}` : ""}`);
}

function safeError(error: unknown): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before reviewing audit evidence.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (error.status === 403) {
      return "Your role cannot review audit evidence in this organization.";
    }
  }
  return "Audit evidence is unavailable. Retry the request or review the API connection.";
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "System";
}

export function AuditWorkbench() {
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [filters, setFilters] = useState<Filters>(readInitialFilters);
  const [draftFilters, setDraftFilters] = useState<Filters>(filters);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;
  const visibleEvents = viewState === "disconnected" || viewState === "unauthenticated" ? [] : events;

  useEffect(() => {
    const controller = new AbortController();
    if (!configuredEndpoint || !getAccessToken()) {
      return () => controller.abort();
    }

    listAuditEvents({ action: filters.action, entityType: filters.entityType, limit: 50, offset: 0 }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setEvents(result.items);
          setTotal(result.total);
          setNextOffset(result.next_offset);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(safeError(error));
          setLoadState("error");
        }
      });

    return () => controller.abort();
  }, [configuredEndpoint, filters, refreshNonce]);

  const handleFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEvents([]);
    setLoadState("idle");
    const next = { action: draftFilters.action.trim(), entityType: draftFilters.entityType.trim() };
    updateLocation(next);
    setFilters(next);
  };

  const handleLoadMore = async () => {
    if (nextOffset === null) {
      return;
    }
    setIsLoadingMore(true);
    try {
      const result = await listAuditEvents({ action: filters.action, entityType: filters.entityType, limit: 50, offset: nextOffset });
      setEvents((current) => [...current, ...result.items]);
      setTotal(result.total);
      setNextOffset(result.next_offset);
    } catch (error: unknown) {
      setLoadError(safeError(error));
    } finally {
      setIsLoadingMore(false);
    }
  };

  const financialCount = visibleEvents.filter((event) => /^(document|payment|ledger|bank_)/.test(event.action)).length;
  const operatorCount = new Set(visibleEvents.map((event) => event.actor_user_id).filter(Boolean)).size;
  const statusLabel = {
    idle: "Loading workspace",
    loading: "Loading live evidence",
    ready: `${total} ${total === 1 ? "event" : "events"} in scope`,
    disconnected: "API not connected",
    unauthenticated: "Sign-in required",
    error: "Evidence unavailable",
  }[viewState];
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy"><p className="eyebrow">Governance</p><h1 className="page-title">Audit & activity</h1><p className="page-subtitle">Review the evidence behind financial and administrative changes with scoped history, correlation lineage and safe payloads.</p></div>
        <div className="page-actions"><StatusBadge tone={statusTone}>{statusLabel}</StatusBadge><button className="button button-secondary" type="button" disabled={visibleEvents.length === 0} onClick={() => exportAuditEvents(visibleEvents)}><Download size={15} aria-hidden="true" /> Export loaded evidence</button></div>
      </header>

      {viewState !== "ready" ? <section className="connection-banner" aria-labelledby="audit-connection-title" role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><ShieldCheck size={19} aria-hidden="true" /><div><strong id="audit-connection-title">{viewState === "error" ? "Audit data needs attention" : "Audit evidence is unavailable until the workspace connects"}</strong><p>{viewState === "disconnected" ? "Connect the API to inspect organization-scoped evidence. No activity records are fabricated in this interface." : viewState === "unauthenticated" ? "Sign in with an organization account before reviewing audit evidence." : viewState === "error" ? loadError : "History respects organization scope, permission policy and server-side redaction."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setEvents([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry audit load</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}</div></section> : null}

      <section className="metric-grid" aria-label="Audit metrics"><DataCard label="Events in scope" value={viewState === "ready" ? String(total) : "—"} meta="Server-counted organization events" icon={History} /><DataCard label="Financial changes loaded" value={viewState === "ready" ? String(financialCount) : "—"} meta="Loaded page · action classification" icon={SlidersHorizontal} /><DataCard label="Active operators loaded" value={viewState === "ready" ? String(operatorCount) : "—"} meta="Distinct actor identities in page" icon={UserRoundCheck} /><DataCard label="Redaction policy" value="Active" meta="Credentials excluded from views" status="Ready" icon={ShieldCheck} /></section>

      <nav className="tab-list" aria-label="Audit sections"><a href="/audit" aria-current="page">Event explorer</a><a href="/audit#financial-controls">Financial controls</a><a href="/audit#access-history">Access history</a></nav>

      <section className="panel" aria-labelledby="audit-event-title"><div className="section-heading"><div className="section-heading-row"><div><h2 id="audit-event-title">Event explorer</h2><p>Search exact server filters without changing the underlying append-only audit record.</p></div><StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Append-only</StatusBadge></div></div>
        <form className="workbench-toolbar" aria-label="Audit event filters" onSubmit={handleFilters}><label className="search-trigger workbench-search" htmlFor="audit-action-filter"><Search size={16} aria-hidden="true" /><span className="visually-hidden">Action filter</span><input id="audit-action-filter" type="search" value={draftFilters.action} onChange={(event) => setDraftFilters((current) => ({ ...current, action: event.target.value }))} placeholder="Filter exact action, e.g. payment.post" disabled={!canUseWorkspace || viewState === "loading"} /></label><label className="search-trigger workbench-search" htmlFor="audit-entity-filter"><Filter size={16} aria-hidden="true" /><span className="visually-hidden">Entity type filter</span><input id="audit-entity-filter" type="search" value={draftFilters.entityType} onChange={(event) => setDraftFilters((current) => ({ ...current, entityType: event.target.value }))} placeholder="Filter entity type" disabled={!canUseWorkspace || viewState === "loading"} /></label><button className="button button-secondary" type="submit" disabled={!canUseWorkspace || viewState === "loading"}><Filter size={15} aria-hidden="true" /> Apply audit filters</button><span className="page-subtitle"><CalendarClock size={14} aria-hidden="true" /> Deterministic pagination</span></form>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll audit events horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Audit event explorer</caption><thead><tr><th scope="col">Timestamp</th><th scope="col">Action</th><th scope="col">Entity</th><th scope="col">Actor</th><th scope="col">Correlation</th><th scope="col">Payload</th></tr></thead><tbody>{visibleEvents.length > 0 ? visibleEvents.map((event) => <tr key={event.id}><td>{formatDateTime(event.created_at)}</td><td><strong>{event.action}</strong></td><td>{event.entity_type}<small className="table-secondary">{shortId(event.entity_id)}</small></td><td>{shortId(event.actor_user_id)}</td><td><code>{event.correlation_id}</code></td><td><code className="audit-payload">{JSON.stringify(event.payload)}</code></td></tr>) : <tr><td className="muted-cell" colSpan={6}>{viewState === "loading" ? "Loading audit events…" : viewState === "error" ? "Audit events unavailable" : viewState === "ready" ? "No audit events to display" : "No connected audit events"}</td></tr>}</tbody></table></div>
        {viewState === "ready" && visibleEvents.length === 0 ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><History size={20} /></span><strong>No audit history to display</strong><p>Connect an authorized organization to inspect immutable activity, financial posting lineage and access events.</p><StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Explorer ready</StatusBadge></div> : null}
        {viewState === "ready" && nextOffset !== null ? <div className="page-actions"><button className="button button-secondary" type="button" onClick={handleLoadMore} disabled={isLoadingMore}>{isLoadingMore ? "Loading…" : "Load more events"}</button><span className="page-subtitle">Showing {visibleEvents.length} of {total}</span></div> : null}
      </section>

      <section className="panel-grid two-column" id="financial-controls"><div className="panel"><div className="section-heading"><h2>Evidence contract</h2><p>Audit data is designed as a control surface, not a generic activity feed.</p></div><div className="audit-policy-list">{policies.map(({ label, detail, icon: Icon }) => <div className="audit-policy" key={label}><span className="audit-policy-icon" aria-hidden="true"><Icon size={16} /></span><span><strong>{label}</strong><small>{detail}</small></span></div>)}</div></div><div className="panel" id="access-history" aria-labelledby="audit-review-title"><div className="section-heading"><div className="section-heading-row"><div><h2 id="audit-review-title">Review posture</h2><p>Use event history to support close, incident response and administrator review.</p></div><StatusBadge tone="success"><CheckCircle2 size={12} aria-hidden="true" /> Policy ready</StatusBadge></div></div><ul className="feature-list"><li><CheckCircle2 size={16} aria-hidden="true" /> Financial actions retain source and actor context.</li><li><CheckCircle2 size={16} aria-hidden="true" /> Filter and pagination are deterministic for repeatable review.</li><li><CheckCircle2 size={16} aria-hidden="true" /> Exports contain only server-redacted loaded evidence.</li></ul></div></section>
    </div>
  );
}
