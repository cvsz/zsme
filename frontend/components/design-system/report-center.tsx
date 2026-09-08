"use client";

import {
  BarChart3,
  Download,
  FileBarChart,
  FileCheck2,
  FileSpreadsheet,
  Landmark,
  LockKeyhole,
  PieChart,
  RefreshCw,
  Search,
  ShieldCheck,
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
import { formatMoney } from "@/lib/documents";
import { getTrialBalance, type TrialBalanceReport, type TrialBalanceRow } from "@/lib/reports";

type ReportDefinition = {
  href: string;
  label: string;
  description: string;
  icon: typeof FileSpreadsheet;
  supported: boolean;
};

const reports: ReportDefinition[] = [
  { href: "/reports/trial-balance", label: "Trial balance", description: "Verify total debits and credits by account.", icon: FileSpreadsheet, supported: true },
  { href: "/reports/profit-loss", label: "Profit & loss", description: "Understand revenue, expenses and operating result.", icon: BarChart3, supported: false },
  { href: "/reports/balance-sheet", label: "Balance sheet", description: "Review assets, liabilities and equity position.", icon: PieChart, supported: false },
  { href: "/reports/general-ledger", label: "General ledger", description: "Drill from account totals to immutable entries.", icon: FileBarChart, supported: false },
  { href: "/reports/aged-receivable", label: "Aged receivable", description: "Track outstanding customer balances and ageing.", icon: Landmark, supported: false },
  { href: "/reports/aged-payable", label: "Aged payable", description: "Track supplier obligations and due dates.", icon: FileCheck2, supported: false },
];

type LoadState = "idle" | "ready" | "error";

function formatReportDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function safeError(error: unknown): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before generating a financial report.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (error.status === 403) {
      return "Your role cannot generate reports in this organization.";
    }
    if (error.status === 409) {
      return "The report request conflicts with the current organization controls.";
    }
  }
  return "The report is unavailable. Retry the request or review the API connection.";
}

function csvCell(value: string): string {
  const safe = /^[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safe.replaceAll('"', '""')}"`;
}

function exportTrialBalance(report: TrialBalanceReport, rows: TrialBalanceRow[]): void {
  if (typeof window === "undefined") {
    return;
  }
  const lines = [
    ["Account code", "Account name", "Account type", "Debit", "Credit", "Balance"].map(csvCell).join(","),
    ...rows.map((row) => [row.account_code, row.account_name || "", row.account_type || "", row.debit, row.credit, row.balance].map(csvCell).join(",")),
    ["TOTAL", "", "", report.total_debit, report.total_credit, ""].map(csvCell).join(","),
  ];
  const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `zsme-trial-balance-${report.from_date}-${report.to_date}.csv`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function updateReportLocation(fromDate: string, toDate: string): void {
  const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  window.history.replaceState(null, "", `/reports/trial-balance?${params.toString()}`);
}

export function ReportCenter({ activeReport }: Readonly<{ activeReport?: string }>) {
  const activeDefinition = reports.find((report) => report.label === activeReport);
  const isTrialBalance = activeDefinition?.supported === true;
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [fromDate, setFromDate] = useState("2026-01-01");
  const [toDate, setToDate] = useState("2026-12-31");
  const [appliedFromDate, setAppliedFromDate] = useState("2026-01-01");
  const [appliedToDate, setAppliedToDate] = useState("2026-12-31");
  const [search, setSearch] = useState("");
  const [report, setReport] = useState<TrialBalanceReport | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [validationError, setValidationError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" | "unsupported" | "overview" = !activeDefinition
    ? "overview"
    : !isTrialBalance
      ? "unsupported"
      : !configuredEndpoint
        ? "disconnected"
        : !getAccessToken()
          ? "unauthenticated"
          : loadState === "idle"
            ? "loading"
            : loadState;

  useEffect(() => {
    const controller = new AbortController();
    if (!isTrialBalance || !configuredEndpoint || !getAccessToken()) {
      return () => controller.abort();
    }
    getTrialBalance(appliedFromDate, appliedToDate, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setReport(result);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setReport(null);
          setLoadError(safeError(error));
          setLoadState("error");
        }
      });
    return () => controller.abort();
  }, [appliedFromDate, appliedToDate, configuredEndpoint, isTrialBalance, refreshNonce]);

  const visibleRows = useMemo(() => {
    if (!report) {
      return [];
    }
    const normalized = search.trim().toLowerCase();
    return report.rows.filter((row) => !normalized || `${row.account_code} ${row.account_name || ""} ${row.account_type || ""}`.toLowerCase().includes(normalized));
  }, [report, search]);

  const handleRunReport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setValidationError("");
    if (!fromDate || !toDate) {
      setValidationError("Select both a start and end date before running the report.");
      return;
    }
    if (fromDate > toDate) {
      setValidationError("The start date must be on or before the end date.");
      return;
    }
    updateReportLocation(fromDate, toDate);
    setReport(null);
    setLoadState("idle");
    setAppliedFromDate(fromDate);
    setAppliedToDate(toDate);
  };

  const balanced = report ? report.total_debit === report.total_credit : false;
  const headerStatus = viewState === "ready" ? "Report ready" : viewState === "loading" ? "Loading report" : viewState === "error" ? "Report unavailable" : viewState === "unsupported" ? "Contract pending" : viewState === "overview" ? "Select a report" : viewState === "unauthenticated" ? "Sign-in required" : "API not connected";
  const headerTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Financial intelligence</p>
          <h1 className="page-title">Reports & insights</h1>
          <p className="page-subtitle">Ledger-derived reporting with clear date scope, source lineage and export-ready contracts.</p>
        </div>
        <div className="page-actions"><StatusBadge tone={headerTone}>{headerStatus}</StatusBadge>{isTrialBalance ? <button className="button button-secondary" type="button" disabled={!report || visibleRows.length === 0} onClick={() => report && exportTrialBalance(report, visibleRows)}><Download size={15} aria-hidden="true" /> Export CSV</button> : null}</div>
      </header>

      {viewState === "unsupported" ? <section className="connection-banner" aria-labelledby="report-contract-title"><div className="connection-banner-copy"><ShieldCheck size={19} aria-hidden="true" /><div><strong id="report-contract-title">This report is governed but not yet exposed by the API</strong><p>Report contract pending</p></div></div><Link className="button button-secondary" href="/settings#connections">Review platform status</Link></section> : viewState !== "ready" && viewState !== "overview" ? <section className="connection-banner" aria-labelledby="reports-connection-title" role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><ShieldCheck size={19} aria-hidden="true" /><div><strong id="reports-connection-title">{viewState === "error" ? "Report data needs attention" : "Reports stay guarded until the workspace connects"}</strong><p>{viewState === "disconnected" ? "Connect the API to generate tenant-scoped reports. No unsupported financial values are fabricated." : viewState === "unauthenticated" ? "Sign in with an organization account before generating reports." : viewState === "error" ? loadError : "Totals are derived from posted ledger lines only and remain reproducible from source records."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setReport(null); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry report</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}</div></section> : null}

      <nav className="report-grid" aria-label="Available financial reports">
        {reports.map(({ href, label, description, icon: Icon, supported }) => <Link className={`report-card${activeReport === label ? " is-active" : ""}`} href={href} key={href}><span className="report-card-icon" aria-hidden="true"><Icon size={19} /></span><span><strong>{label}</strong><small>{description}</small></span><StatusBadge tone={supported ? "success" : "warning"}>{supported ? "Available" : "Contract pending"}</StatusBadge></Link>)}
      </nav>

      <section className="panel" aria-labelledby="report-preview-title">
        <div className="section-heading"><div className="section-heading-row"><div><h2 id="report-preview-title">{activeReport || "Report preview"}</h2><p>{activeDefinition ? activeDefinition.description : "Choose a report above, then set date, organization and account filters."}</p></div><StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Posted ledger only</StatusBadge></div></div>
        {isTrialBalance ? <>
          <form className="workbench-toolbar" aria-label="Trial balance controls" onSubmit={handleRunReport}><label className="field-inline" htmlFor="report-search"><Search size={15} aria-hidden="true" /><span className="visually-hidden">Search report accounts</span><input id="report-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter by account" disabled={viewState !== "ready" && viewState !== "loading"} /></label><label className="field-inline" htmlFor="from-date"><span>From</span><input id="from-date" aria-label="From date" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label><label className="field-inline" htmlFor="to-date"><span>To</span><input id="to-date" aria-label="To date" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label><button className="button button-primary" type="submit" disabled={!canUseWorkspace || viewState === "loading"}><RefreshCw size={15} aria-hidden="true" /> Run report</button></form>
          {validationError ? <p className="form-message" role="alert">{validationError}</p> : null}
          {report ? <section className="metric-grid" aria-label="Trial balance metrics"><DataCard label="Total debit" value={formatMoney(report.total_debit)} meta={`${formatReportDate(report.from_date)} – ${formatReportDate(report.to_date)}`} status="Posted ledger" icon={FileSpreadsheet} /><DataCard label="Total credit" value={formatMoney(report.total_credit)} meta="Posted ledger" status="Posted ledger" icon={BarChart3} /><DataCard label="Accounts in report" value={String(report.rows.length)} meta="Grouped account codes" status="Derived" icon={FileBarChart} /><DataCard label="Balance check" value={balanced ? "Balanced" : "Review"} meta="Debit equals credit" status={balanced ? "Control passed" : "Control failed"} icon={balanced ? ShieldCheck : LockKeyhole} /></section> : null}
          <div className="data-table-wrap" tabIndex={0} aria-label="Scroll trial balance table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Trial balance from {appliedFromDate} to {appliedToDate}</caption><thead><tr><th scope="col">Account</th><th scope="col">Type</th><th scope="col">Debit</th><th scope="col">Credit</th><th scope="col">Balance</th></tr></thead><tbody>{visibleRows.length > 0 ? visibleRows.map((row) => <tr key={row.account_code}><td><strong>{row.account_code}</strong><small className="table-secondary">{row.account_name || "Unnamed account"}</small></td><td>{row.account_type || "—"}</td><td>{formatMoney(row.debit)}</td><td>{formatMoney(row.credit)}</td><td>{formatMoney(row.balance)}</td></tr>) : <tr><td className="muted-cell" colSpan={5}>{viewState === "loading" ? "Generating trial balance…" : viewState === "error" ? "Trial balance unavailable" : viewState === "ready" ? "No accounts match the current filter" : "No connected report data"}</td></tr>}</tbody></table></div>
          {viewState === "ready" && visibleRows.length === 0 ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><FileSpreadsheet size={20} /></span><strong>No report rows to display</strong><p>The selected posted-ledger scope contains no account rows, or the current filter excludes them.</p><StatusBadge tone="info">No fabricated values</StatusBadge></div> : null}
        </> : <div className="empty-state"><span className="empty-state-icon" aria-hidden="true"><FileSpreadsheet size={20} /></span><strong>{activeReport ? "Report contract pending" : "Choose a report to begin"}</strong><p>{activeReport ? "No unsupported financial values are fabricated." : "Select Trial balance to generate the currently supported ledger-derived report."}</p>{!activeReport ? <Link className="button button-secondary" href="/reports/trial-balance">Open trial balance</Link> : null}</div>}
      </section>
    </div>
  );
}
