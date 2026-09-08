"use client";

import {
  Banknote,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  FileCheck2,
  FileText,
  Landmark,
  Link2,
  RefreshCw,
  ShieldCheck,
  UsersRound,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";

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
import { formatDashboardMoney, getDashboardSummary, type DashboardSummary } from "@/lib/dashboard";

type LoadState = "idle" | "ready" | "error";
const DEFAULT_AS_OF = "2026-09-08";

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "System";
}

function safeError(error: unknown): string {
  if (error instanceof ApiConfigurationError) return "Connect the API endpoint before loading executive metrics.";
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your role cannot review dashboard metrics in this organization.";
  }
  return "Dashboard data is unavailable. Retry the request or review the API connection.";
}

export default function DashboardPage() {
  const configuredEndpoint = useSyncExternalStore(subscribeToApiBaseUrl, getApiBaseUrl, getServerApiBaseUrl);
  const [asOf, setAsOf] = useState(DEFAULT_AS_OF);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;

  useEffect(() => {
    const controller = new AbortController();
    if (!configuredEndpoint || !getAccessToken()) return () => controller.abort();
    getDashboardSummary(asOf, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setSummary(result);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setSummary(null);
          setLoadError(safeError(error));
          setLoadState("error");
        }
      });
    return () => controller.abort();
  }, [asOf, configuredEndpoint, refreshNonce]);

  const statusLabel = viewState === "ready" && summary ? `Live as of ${formatDate(summary.as_of)}` : viewState === "loading" ? "Loading live metrics" : viewState === "error" ? "Data unavailable" : viewState === "unauthenticated" ? "Sign-in required" : "API not connected";
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";
  const currency = summary?.currency_code || "THB";

  return (
    <div className="page-stack">
      <header className="page-header"><div className="page-header-copy"><p className="eyebrow">Command center</p><h1 className="page-title">Business control center</h1><p className="page-subtitle">A calm, auditable view of business operations derived from server-side ledger and control contracts.</p></div><div className="page-actions"><StatusBadge tone={statusTone}>{statusLabel}</StatusBadge><button className="button button-secondary" type="button" disabled={!canUseWorkspace || viewState === "loading"} onClick={() => { setSummary(null); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Refresh data</button></div></header>

      {viewState !== "ready" ? <section className="connection-banner" aria-label={viewState === "error" ? "Dashboard data needs attention" : "Dashboard connection status"} role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><Link2 size={19} aria-hidden="true" /><div><strong>{viewState === "error" ? "Dashboard data needs attention" : "Data source not configured"}</strong><p>{viewState === "disconnected" ? "Connect the ZSME API and an authorized organization to activate financial totals. No values are fabricated in this interface." : viewState === "unauthenticated" ? "Sign in with an organization account before reviewing executive metrics." : viewState === "error" ? loadError : "Financial totals, workflows and live reporting are loading from the authorized workspace."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setSummary(null); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry dashboard</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-primary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection settings" : "Go to sign in"}</Link> : null}</div></section> : null}

      <section className="metric-grid" aria-label="Key business metrics"><DataCard label="Cash position" value={viewState === "ready" ? formatDashboardMoney(summary?.cash_position || null, currency) : "—"} meta={`${currency} · posted bank-mapped ledger`} status={viewState === "ready" ? summary?.cash_position === null ? "No bank mapping" : "Derived" : "Awaiting API"} icon={WalletCards} /><DataCard label="Receivables" value={viewState === "ready" ? formatDashboardMoney(summary?.receivables || "0.00", currency) : "—"} meta={`${currency} · posted invoices less posted allocations`} status={viewState === "ready" ? `${summary?.open_invoices || 0} open` : "Awaiting API"} icon={Banknote} /><DataCard label="Payables" value={viewState === "ready" ? formatDashboardMoney(summary?.payables || "0.00", currency) : "—"} meta={`${currency} · posted bills less posted allocations`} status={viewState === "ready" ? `${summary?.open_bills || 0} open` : "Awaiting API"} icon={Landmark} /><DataCard label="Unmatched banking" value={viewState === "ready" ? String(summary?.unmatched_bank_transactions || 0) : "—"} meta="Imported movements requiring review" status={viewState === "ready" ? summary?.unmatched_bank_transactions ? `${summary.unmatched_bank_transactions} unmatched` : "Clear" : "Not evaluated"} icon={CircleAlert} /></section>

      <section className="metric-grid" aria-label="Workspace operating metrics"><DataCard label="Customers" value={viewState === "ready" ? String(summary?.customer_count || 0) : "—"} meta="Active organization partners" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={UsersRound} /><DataCard label="Vendors" value={viewState === "ready" ? String(summary?.vendor_count || 0) : "—"} meta="Active organization partners" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={FileText} /><DataCard label="Data lineage" value={viewState === "ready" ? "Traceable" : "—"} meta="Source and correlation retained" status={viewState === "ready" ? "Audit ready" : "Not evaluated"} icon={ShieldCheck} /><DataCard label="As-of date" value={viewState === "ready" ? formatDate(summary?.as_of || asOf) : "—"} meta="Dashboard reporting boundary" status={viewState === "ready" ? "Explicit" : "Awaiting API"} icon={CalendarClock} /></section>

      <div className="panel-grid two-column"><section className="panel" aria-label="Recent activity" aria-labelledby="activity-title"><div className="section-heading"><h2 id="activity-title">Recent activity</h2><p>Server-selected audit activity for the connected organization.</p></div><div className="data-table-wrap" tabIndex={0} aria-label="Scroll recent activity table horizontally"><table className="data-table"><caption>Recent accounting and operational activity</caption><thead><tr><th scope="col">Event</th><th scope="col">Entity</th><th scope="col">Correlation</th><th scope="col">Updated</th></tr></thead><tbody>{viewState === "ready" && summary?.recent_activity.length ? summary.recent_activity.map((event) => <tr key={event.id}><td><strong>{event.action}</strong></td><td>{event.entity_type}<small className="table-secondary">{shortId(event.entity_id)}</small></td><td><code>{event.correlation_id}</code></td><td>{formatDateTime(event.created_at)}</td></tr>) : <tr><td className="muted-cell" colSpan={4}>{viewState === "loading" ? "Loading recent activity…" : viewState === "error" ? "Activity unavailable" : viewState === "ready" ? "No recent activity" : "No connected events"}</td></tr>}</tbody></table></div>{viewState === "ready" ? <div className="page-actions"><Link className="button button-secondary" href="/audit">Open audit explorer</Link></div> : null}</section><section className="panel" aria-labelledby="readiness-title"><div className="section-heading"><h2 id="readiness-title">Readiness controls</h2><p>Enterprise guardrails remain visible during every operating cycle.</p></div><ul className="feature-list"><li><CheckCircle2 size={16} aria-hidden="true" /> Double-entry validation at the ledger boundary.</li><li><CheckCircle2 size={16} aria-hidden="true" /> Tenant-scoped authorization and server-redacted audit evidence.</li><li><CheckCircle2 size={16} aria-hidden="true" /> Posted-only metrics with explicit as-of dates and currency.</li><li><CheckCircle2 size={16} aria-hidden="true" /> Review unmatched bank activity before close.</li></ul><div className="page-actions"><Link className="button button-secondary" href="/reports/trial-balance"><BarChart3 size={15} aria-hidden="true" /> Open trial balance</Link><Link className="button button-secondary" href="/settings#connections"><FileCheck2 size={15} aria-hidden="true" /> Review controls</Link></div></section></div>
    </div>
  );
}
