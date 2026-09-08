"use client";

import {
  CalendarClock,
  CheckCircle2,
  FilePlus2,
  Filter,
  LockKeyhole,
  Percent,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState, useSyncExternalStore } from "react";

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
import {
  createTaxRate,
  createTaxRateIdempotencyKey,
  listTaxRates,
  type TaxRateRule,
  type TaxType,
} from "@/lib/tax";

type LoadState = "idle" | "ready" | "error";

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function safeError(error: unknown, action: "load" | "create"): string {
  if (error instanceof ApiConfigurationError) return "Connect the API endpoint before managing tax rules.";
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Sign in again to continue.";
    if (error.status === 403) return `Your role cannot ${action} tax rules in this organization.`;
    if (error.status === 409) return "The tax rule conflicts with an existing effective-dated rule.";
  }
  return action === "load" ? "Tax rules are unavailable. Retry the request or review the API connection." : "Tax rule could not be created. Review the fields and try again.";
}

export function TaxWorkbench() {
  const configuredEndpoint = useSyncExternalStore(subscribeToApiBaseUrl, getApiBaseUrl, getServerApiBaseUrl);
  const [rules, setRules] = useState<TaxRateRule[]>([]);
  const [taxType, setTaxType] = useState<TaxType | "">("");
  const [search, setSearch] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
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
    listTaxRates(taxType || undefined, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setRules(result);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setRules([]);
          setLoadError(safeError(error, "load"));
          setLoadState("error");
        }
      });
    return () => controller.abort();
  }, [configuredEndpoint, refreshNonce, taxType]);

  const visibleRules = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return rules.filter((rule) => !normalized || `${rule.code} ${rule.name} ${rule.tax_type}`.toLowerCase().includes(normalized));
  }, [rules, search]);
  const vatCount = rules.filter((rule) => rule.tax_type === "vat").length;
  const withholdingCount = rules.filter((rule) => rule.tax_type === "withholding").length;

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    const effectiveTo = String(data.get("effective_to") || "").trim();
    setIsCreating(true);
    try {
      const created = await createTaxRate({
        tax_type: String(data.get("tax_type") || "vat") as TaxType,
        code: String(data.get("code") || "").trim(),
        name: String(data.get("name") || "").trim(),
        rate: String(data.get("rate") || "0").trim(),
        effective_from: String(data.get("effective_from") || ""),
        effective_to: effectiveTo || undefined,
      }, createTaxRateIdempotencyKey());
      setRules((current) => [...current, created].sort((left, right) => left.code.localeCompare(right.code)));
      setIsCreateOpen(false);
      setNotice("Tax rule created");
    } catch (error: unknown) {
      setActionError(safeError(error, "create"));
    } finally {
      setIsCreating(false);
    }
  };

  const statusLabel = viewState === "ready" ? `${rules.length} active tax rule${rules.length === 1 ? "" : "s"}` : viewState === "loading" ? "Loading tax rules" : viewState === "error" ? "Data unavailable" : viewState === "unauthenticated" ? "Sign-in required" : "API not connected";
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  return (
    <div className="page-stack">
      <header className="page-header"><div className="page-header-copy"><p className="eyebrow">Thailand-ready controls</p><h1 className="page-title">Tax configuration</h1><p className="page-subtitle">Manage effective-dated VAT and withholding-tax rules without changing posted accounting history.</p></div><div className="page-actions"><StatusBadge tone={statusTone}>{statusLabel}</StatusBadge><button className="button button-primary" type="button" disabled={!canUseWorkspace || viewState !== "ready"} onClick={() => { setActionError(""); setIsCreateOpen(true); }}><FilePlus2 size={15} aria-hidden="true" /> Add tax rule</button></div></header>

      {viewState !== "ready" ? <section className="connection-banner" aria-labelledby="tax-connection-title" role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><Percent size={19} aria-hidden="true" /><div><strong id="tax-connection-title">{viewState === "error" ? "Tax data needs attention" : "Tax configuration stays guarded until the workspace connects"}</strong><p>{viewState === "disconnected" ? "Connect the API to load organization tax rules. No rates are fabricated in this interface." : viewState === "unauthenticated" ? "Sign in with an organization account before reviewing or changing tax rules." : viewState === "error" ? loadError : "Rules are organization-scoped, effective-dated, duplicate-safe and audited by the server."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setRules([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry tax load</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}</div></section> : null}
      {notice ? <p className="form-message" role="status" aria-live="polite">{notice}</p> : null}{actionError ? <p className="form-message" role="alert">{actionError}</p> : null}

      {isCreateOpen ? <section className="panel" aria-labelledby="create-tax-title"><div className="section-heading-row"><div className="section-heading"><h2 id="create-tax-title">Add tax rule</h2><p>Effective dates cannot overlap an active rule with the same tax type and code.</p></div><button className="icon-button" type="button" aria-label="Close create tax rule form" onClick={() => setIsCreateOpen(false)}><X size={17} aria-hidden="true" /></button></div><form className="form-grid" onSubmit={handleCreate}><div className="panel-grid two-column"><div className="field"><label htmlFor="tax-type">Tax type</label><select id="tax-type" name="tax_type" defaultValue="vat"><option value="vat">VAT</option><option value="withholding">Withholding tax</option></select></div><div className="field"><label htmlFor="tax-code">Tax code</label><input id="tax-code" name="code" required maxLength={64} placeholder="VAT7" /></div><div className="field"><label htmlFor="tax-name">Tax rule name</label><input id="tax-name" name="name" required maxLength={200} placeholder="Value added tax 7%" /></div><div className="field"><label htmlFor="tax-rate">Rate (%)</label><input id="tax-rate" name="rate" type="number" required min="0" max="100" step="0.01" defaultValue="7" /></div><div className="field"><label htmlFor="effective-from">Effective from</label><input id="effective-from" name="effective_from" type="date" required defaultValue="2026-01-01" /></div><div className="field"><label htmlFor="effective-to">Effective to</label><input id="effective-to" name="effective_to" type="date" /><small>Leave blank for an open-ended rule.</small></div></div><div className="page-actions"><button className="button button-primary" type="submit" disabled={isCreating} aria-busy={isCreating}><FilePlus2 size={15} aria-hidden="true" /> {isCreating ? "Creating…" : "Create tax rule"}</button><button className="button button-secondary" type="button" onClick={() => setIsCreateOpen(false)}>Cancel</button></div></form></section> : null}

      <section className="metric-grid" aria-label="Tax metrics"><DataCard label="VAT rules" value={viewState === "ready" ? String(vatCount) : "—"} meta="Active effective-dated rules" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={Percent} /><DataCard label="Withholding rules" value={viewState === "ready" ? String(withholdingCount) : "—"} meta="Active effective-dated rules" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={Filter} /><DataCard label="Effective-date integrity" value={viewState === "ready" ? "Ready" : "—"} meta="Overlap validation on server" status={viewState === "ready" ? "Enforced" : "Not evaluated"} icon={CheckCircle2} /><DataCard label="Tax posting boundary" value="Protected" meta="Source documents determine ledger effects" status="Server enforced" icon={LockKeyhole} /></section>

      <section className="panel" aria-label="Tax rule register" aria-labelledby="tax-register-title"><div className="section-heading"><div className="section-heading-row"><div><h2 id="tax-register-title">Tax rule register</h2><p>Rates are configuration inputs only; statutory submission remains a separate validated adapter.</p></div><StatusBadge tone="info"><ShieldCheck size={12} aria-hidden="true" /> Tenant scoped</StatusBadge></div></div><div className="workbench-toolbar"><label className="search-trigger workbench-search" htmlFor="tax-search"><Search size={16} aria-hidden="true" /><span className="visually-hidden">Search tax rules</span><input id="tax-search" type="search" placeholder="Search code or name" value={search} onChange={(event) => setSearch(event.target.value)} disabled={!canUseWorkspace || viewState !== "ready"} /></label><label className="field-inline" htmlFor="tax-type-filter"><span className="visually-hidden">Filter tax type</span><select id="tax-type-filter" value={taxType} onChange={(event) => setTaxType(event.target.value as TaxType | "")} disabled={!canUseWorkspace || viewState !== "ready"}><option value="">All tax types</option><option value="vat">VAT</option><option value="withholding">Withholding tax</option></select></label><button className="button button-secondary" type="button" disabled={!canUseWorkspace || viewState === "loading"} onClick={() => { setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Refresh</button></div><div className="data-table-wrap" tabIndex={0} aria-label="Scroll tax rule table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Tax rule register</caption><thead><tr><th scope="col">Code</th><th scope="col">Rule</th><th scope="col">Type</th><th scope="col">Rate</th><th scope="col">Effective range</th><th scope="col">Version</th></tr></thead><tbody>{visibleRules.length > 0 ? visibleRules.map((rule) => <tr key={rule.id}><td><strong>{rule.code}</strong></td><td>{rule.name}</td><td>{rule.tax_type === "vat" ? "VAT" : "Withholding tax"}</td><td><strong>{Number(rule.rate).toFixed(2)}%</strong></td><td>{formatDate(rule.effective_from)} – {rule.effective_to ? formatDate(rule.effective_to) : "Open ended"}</td><td>{rule.version}</td></tr>) : <tr><td className="muted-cell" colSpan={6}>{viewState === "loading" ? "Loading tax rules…" : viewState === "error" ? "Tax rules unavailable" : viewState === "ready" ? "No tax rules match the current filter" : "No connected tax rules"}</td></tr>}</tbody></table></div>{viewState === "ready" && visibleRules.length === 0 ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><CalendarClock size={20} /></span><strong>No tax rules to display</strong><p>Add an effective-dated VAT or withholding-tax rule for this organization.</p><StatusBadge tone="info">Ready to configure</StatusBadge></div> : null}</section>
    </div>
  );
}
