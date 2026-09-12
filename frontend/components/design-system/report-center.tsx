"use client";

import {
  ArrowDownLeft,
  ArrowUpRight,
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
  type LucideIcon,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, type ReactNode, useEffect, useMemo, useState, useSyncExternalStore } from "react";

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
import {
  getAgedPayable,
  getAgedReceivable,
  getBalanceSheet,
  getCashFlow,
  getGeneralLedger,
  getProfitLoss,
  getTrialBalance,
  type AccountReportRow,
  type AgedDocumentRow,
  type AgedReport,
  type BalanceSheetReport,
  type CashFlowReport,
  type GeneralLedgerReport,
  type ProfitLossReport,
  type TrialBalanceReport,
} from "@/lib/reports";

type ReportKind =
  | "trial-balance"
  | "profit-loss"
  | "balance-sheet"
  | "general-ledger"
  | "cash-flow"
  | "aged-receivable"
  | "aged-payable";

type ReportDefinition = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
  kind: ReportKind;
  dateScope: "range" | "as-of";
};

type ReportPayload =
  | TrialBalanceReport
  | ProfitLossReport
  | BalanceSheetReport
  | GeneralLedgerReport
  | CashFlowReport
  | AgedReport;

const reports: ReportDefinition[] = [
  { href: "/reports/trial-balance", label: "Trial balance", description: "Verify total debits and credits by account.", icon: FileSpreadsheet, kind: "trial-balance", dateScope: "range" },
  { href: "/reports/profit-loss", label: "Profit & loss", description: "Understand revenue, expenses and operating result.", icon: BarChart3, kind: "profit-loss", dateScope: "range" },
  { href: "/reports/balance-sheet", label: "Balance sheet", description: "Review assets, liabilities and equity position.", icon: PieChart, kind: "balance-sheet", dateScope: "as-of" },
  { href: "/reports/general-ledger", label: "General ledger", description: "Drill from account totals to immutable entries.", icon: FileBarChart, kind: "general-ledger", dateScope: "range" },
  { href: "/reports/cash-flow", label: "Cash flow", description: "Review direct mapped cash-account ledger movement.", icon: WalletCards, kind: "cash-flow", dateScope: "range" },
  { href: "/reports/aged-receivable", label: "Aged receivable", description: "Track outstanding customer balances and ageing.", icon: Landmark, kind: "aged-receivable", dateScope: "as-of" },
  { href: "/reports/aged-payable", label: "Aged payable", description: "Track supplier obligations and due dates.", icon: FileCheck2, kind: "aged-payable", dateScope: "as-of" },
];

type LoadState = "idle" | "ready" | "error";

function formatReportDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function formatBucket(value: AgedDocumentRow["bucket"]): string {
  return {
    current: "Current",
    "1_30": "1–30 days",
    "31_60": "31–60 days",
    "61_90": "61–90 days",
    over_90: "Over 90 days",
  }[value];
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…`;
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

function csvCell(value: string | number | null | undefined): string {
  const text = String(value ?? "");
  const safe = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replaceAll('"', '""')}"`;
}

function downloadCsv(filename: string, rows: Array<Array<string | number | null | undefined>>): void {
  if (typeof window === "undefined") {
    return;
  }
  const lines = rows.map((row) => row.map(csvCell).join(","));
  const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function exportReport(kind: ReportKind, report: ReportPayload): void {
  if (kind === "trial-balance") {
    const data = report as TrialBalanceReport;
    downloadCsv(`zsme-trial-balance-${data.from_date}-${data.to_date}.csv`, [
      ["Account code", "Account name", "Account type", "Debit", "Credit", "Balance"],
      ...data.rows.map((row) => [row.account_code, row.account_name || "", row.account_type || "", row.debit, row.credit, row.balance]),
      ["TOTAL", "", "", data.total_debit, data.total_credit, ""],
    ]);
    return;
  }
  if (kind === "profit-loss") {
    const data = report as ProfitLossReport;
    downloadCsv(`zsme-profit-loss-${data.from_date}-${data.to_date}.csv`, [
      ["Account code", "Account name", "Amount"],
      ...data.rows.map((row) => [row.account_code, row.account_name || "", row.amount]),
      ["TOTAL REVENUE", "", data.total_revenue],
      ["TOTAL EXPENSES", "", data.total_expenses],
      ["NET INCOME", "", data.net_income],
    ]);
    return;
  }
  if (kind === "balance-sheet") {
    const data = report as BalanceSheetReport;
    downloadCsv(`zsme-balance-sheet-${data.as_of}.csv`, [
      ["Section", "Account code", "Account name", "Amount"],
      ...data.assets.map((row) => ["Assets", row.account_code, row.account_name || "", row.amount]),
      ...data.liabilities.map((row) => ["Liabilities", row.account_code, row.account_name || "", row.amount]),
      ...data.equity.map((row) => ["Equity", row.account_code, row.account_name || "", row.amount]),
      ["TOTAL ASSETS", "", "", data.total_assets],
      ["TOTAL LIABILITIES", "", "", data.total_liabilities],
      ["TOTAL EQUITY", "", "", data.total_equity],
      ["NET INCOME", "", "", data.net_income],
      ["TOTAL LIABILITIES + EQUITY", "", "", data.total_liabilities_and_equity],
    ]);
    return;
  }
  if (kind === "general-ledger") {
    const data = report as GeneralLedgerReport;
    downloadCsv(`zsme-general-ledger-${data.from_date}-${data.to_date}.csv`, [
      ["Date", "Reference", "Account code", "Memo", "Source", "Debit", "Credit"],
      ...data.rows.map((row) => [row.journal_date, row.reference, row.account_code, row.memo || "", row.source_type || "", row.debit, row.credit]),
      ["TOTAL", "", "", "", "", data.total_debit, data.total_credit],
    ]);
    return;
  }
  if (kind === "cash-flow") {
    const data = report as CashFlowReport;
    downloadCsv(`zsme-cash-flow-${data.from_date}-${data.to_date}.csv`, [
      ["Account code", "Account name", "Opening balance", "Inflows", "Outflows", "Net change", "Closing balance"],
      ...data.rows.map((row) => [row.account_code, row.account_name || "", row.opening_balance, row.inflow, row.outflow, row.net_change, row.closing_balance]),
      ["TOTAL", "", data.opening_cash, data.total_inflow, data.total_outflow, data.net_change, data.closing_cash],
    ]);
    return;
  }
  const data = report as AgedReport;
  const label = kind === "aged-receivable" ? "aged-receivable" : "aged-payable";
  downloadCsv(`zsme-${label}-${data.as_of}.csv`, [
    ["Document", "Partner ID", "Issue date", "Due date", "Bucket", "Total", "Allocated", "Outstanding"],
    ...data.rows.map((row) => [row.document_number, row.partner_id, row.issue_date, row.due_date, formatBucket(row.bucket), row.total, row.allocated, row.outstanding]),
    ["TOTAL OUTSTANDING", "", "", "", "", "", "", data.total_outstanding],
  ]);
}

function getReport(
  kind: ReportKind,
  fromDate: string,
  toDate: string,
  asOfDate: string,
  signal: AbortSignal,
): Promise<ReportPayload> {
  switch (kind) {
    case "trial-balance":
      return getTrialBalance(fromDate, toDate, signal);
    case "profit-loss":
      return getProfitLoss(fromDate, toDate, signal);
    case "balance-sheet":
      return getBalanceSheet(asOfDate, signal);
    case "general-ledger":
      return getGeneralLedger(fromDate, toDate, signal);
    case "cash-flow":
      return getCashFlow(fromDate, toDate, signal);
    case "aged-receivable":
      return getAgedReceivable(asOfDate, signal);
    case "aged-payable":
      return getAgedPayable(asOfDate, signal);
  }
}

function matchesSearch(value: string, search: string): boolean {
  return !search || value.toLowerCase().includes(search);
}

function renderAccountRows(rows: AccountReportRow[], section: string, search: string): ReactNode {
  const visibleRows = rows.filter((row) => matchesSearch(`${row.account_code} ${row.account_name || ""} ${section}`, search));
  return visibleRows.map((row) => (
    <tr key={`${section}-${row.account_code}`}>
      <td>{section}</td>
      <td><strong>{row.account_code}</strong><small className="table-secondary">{row.account_name || "Unnamed account"}</small></td>
      <td>{formatMoney(row.amount)}</td>
    </tr>
  ));
}

export function ReportCenter({ activeReport }: Readonly<{ activeReport?: string }>) {
  const activeDefinition = reports.find((report) => report.label === activeReport);
  const reportKind = activeDefinition?.kind;
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const authenticated = Boolean(getAccessToken());
  const currentYear = new Date().getFullYear();
  const defaultFromDate = `${currentYear}-01-01`;
  const defaultToDate = `${currentYear}-12-31`;
  const [fromDate, setFromDate] = useState(defaultFromDate);
  const [toDate, setToDate] = useState(defaultToDate);
  const [asOfDate, setAsOfDate] = useState(defaultToDate);
  const [appliedFromDate, setAppliedFromDate] = useState(defaultFromDate);
  const [appliedToDate, setAppliedToDate] = useState(defaultToDate);
  const [appliedAsOfDate, setAppliedAsOfDate] = useState(defaultToDate);
  const [search, setSearch] = useState("");
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [reportKindForData, setReportKindForData] = useState<ReportKind | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [validationError, setValidationError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);

  const canUseWorkspace = Boolean(configuredEndpoint && authenticated);
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" | "overview" = !activeDefinition
    ? "overview"
    : !configuredEndpoint
      ? "disconnected"
      : !authenticated
        ? "unauthenticated"
        : loadState === "idle"
          ? "loading"
          : loadState;

  useEffect(() => {
    const controller = new AbortController();
    if (!reportKind || !configuredEndpoint || !authenticated) {
      return () => controller.abort();
    }
    getReport(reportKind, appliedFromDate, appliedToDate, appliedAsOfDate, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setReport(result);
          setReportKindForData(reportKind);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setReport(null);
          setReportKindForData(null);
          setLoadError(safeError(error));
          setLoadState("error");
        }
      });
    return () => controller.abort();
  }, [appliedAsOfDate, appliedFromDate, appliedToDate, authenticated, configuredEndpoint, refreshNonce, reportKind]);

  const normalizedSearch = search.trim().toLowerCase();
  const currentReport = reportKind && reportKindForData === reportKind ? report : null;
  const trialReport = reportKind === "trial-balance" ? currentReport as TrialBalanceReport | null : null;
  const profitLossReport = reportKind === "profit-loss" ? currentReport as ProfitLossReport | null : null;
  const balanceSheetReport = reportKind === "balance-sheet" ? currentReport as BalanceSheetReport | null : null;
  const generalLedgerReport = reportKind === "general-ledger" ? currentReport as GeneralLedgerReport | null : null;
  const cashFlowReport = reportKind === "cash-flow" ? currentReport as CashFlowReport | null : null;
  const agedReport = reportKind === "aged-receivable" || reportKind === "aged-payable" ? currentReport as AgedReport | null : null;

  const visibleTrialRows = useMemo(
    () => trialReport?.rows.filter((row) => matchesSearch(`${row.account_code} ${row.account_name || ""} ${row.account_type || ""}`, normalizedSearch)) || [],
    [normalizedSearch, trialReport],
  );
  const visibleProfitLossRows = useMemo(
    () => profitLossReport?.rows.filter((row) => matchesSearch(`${row.account_code} ${row.account_name || ""}`, normalizedSearch)) || [],
    [normalizedSearch, profitLossReport],
  );
  const visibleGeneralLedgerRows = useMemo(
    () => generalLedgerReport?.rows.filter((row) => matchesSearch(`${row.reference} ${row.account_code} ${row.memo || ""} ${row.source_type || ""}`, normalizedSearch)) || [],
    [generalLedgerReport, normalizedSearch],
  );
  const visibleCashFlowRows = useMemo(
    () => cashFlowReport?.rows.filter((row) => matchesSearch(`${row.account_code} ${row.account_name || ""}`, normalizedSearch)) || [],
    [cashFlowReport, normalizedSearch],
  );
  const visibleAgedRows = useMemo(
    () => agedReport?.rows.filter((row) => matchesSearch(`${row.document_number} ${row.partner_id} ${row.bucket}`, normalizedSearch)) || [],
    [agedReport, normalizedSearch],
  );

  const handleRunReport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setValidationError("");
    if (!activeDefinition) {
      return;
    }
    if (activeDefinition.dateScope === "range") {
      if (!fromDate || !toDate) {
        setValidationError("Select both a start and end date before running the report.");
        return;
      }
      if (fromDate > toDate) {
        setValidationError("The start date must be on or before the end date.");
        return;
      }
      setAppliedFromDate(fromDate);
      setAppliedToDate(toDate);
      const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
      window.history.replaceState(null, "", `${activeDefinition.href}?${params.toString()}`);
    } else {
      if (!asOfDate) {
        setValidationError("Select an as-of date before running the report.");
        return;
      }
      setAppliedAsOfDate(asOfDate);
      const params = new URLSearchParams({ as_of: asOfDate });
      window.history.replaceState(null, "", `${activeDefinition.href}?${params.toString()}`);
    }
    setReport(null);
    setReportKindForData(null);
    setLoadState("idle");
  };

  const reportIsBalanced = trialReport
    ? trialReport.total_debit === trialReport.total_credit
    : generalLedgerReport
      ? generalLedgerReport.total_debit === generalLedgerReport.total_credit
      : balanceSheetReport
        ? balanceSheetReport.total_assets === balanceSheetReport.total_liabilities_and_equity
        : false;
  const headerStatus = viewState === "ready" ? "Report ready" : viewState === "loading" ? "Loading report" : viewState === "error" ? "Report unavailable" : viewState === "overview" ? "Select a report" : viewState === "unauthenticated" ? "Sign-in required" : "API not connected";
  const headerTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  let reportBody: ReactNode;
  if (!activeDefinition) {
    reportBody = <div className="empty-state"><span className="empty-state-icon" aria-hidden="true"><FileSpreadsheet size={20} /></span><strong>Choose a report to begin</strong><p>Each report is derived from posted, tenant-scoped records and exposes its source date scope.</p><Link className="button button-secondary" href="/reports/trial-balance">Open trial balance</Link></div>;
  } else {
    reportBody = <>
      <form className="workbench-toolbar" aria-label={`${activeDefinition.label} controls`} onSubmit={handleRunReport}>
        <label className="field-inline" htmlFor="report-search"><Search size={15} aria-hidden="true" /><span className="visually-hidden">Search report rows</span><input id="report-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter report rows" disabled={viewState !== "ready" && viewState !== "loading"} /></label>
        {activeDefinition.dateScope === "range" ? <><label className="field-inline" htmlFor="from-date"><span>From</span><input id="from-date" aria-label="From date" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label><label className="field-inline" htmlFor="to-date"><span>To</span><input id="to-date" aria-label="To date" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label></> : <label className="field-inline" htmlFor="as-of-date"><span>As of</span><input id="as-of-date" aria-label="As-of date" type="date" value={asOfDate} onChange={(event) => setAsOfDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label>}
        <button className="button button-primary" type="submit" disabled={!canUseWorkspace || viewState === "loading"}><RefreshCw size={15} aria-hidden="true" /> Run report</button>
      </form>
      {validationError ? <p className="form-message" role="alert">{validationError}</p> : null}
      {trialReport ? <section className="metric-grid" aria-label="Trial balance metrics"><DataCard label="Total debit" value={formatMoney(trialReport.total_debit)} meta={`${formatReportDate(trialReport.from_date)} – ${formatReportDate(trialReport.to_date)}`} status="Posted ledger" icon={FileSpreadsheet} /><DataCard label="Total credit" value={formatMoney(trialReport.total_credit)} meta="Posted ledger" status="Posted ledger" icon={BarChart3} /><DataCard label="Accounts in report" value={String(trialReport.rows.length)} meta="Grouped account codes" status="Derived" icon={FileBarChart} /><DataCard label="Balance check" value={reportIsBalanced ? "Balanced" : "Review"} meta="Debit equals credit" status={reportIsBalanced ? "Control passed" : "Control failed"} icon={reportIsBalanced ? ShieldCheck : LockKeyhole} /></section> : null}
      {profitLossReport ? <section className="metric-grid" aria-label="Profit and loss metrics"><DataCard label="Revenue" value={formatMoney(profitLossReport.total_revenue)} meta={`${formatReportDate(profitLossReport.from_date)} – ${formatReportDate(profitLossReport.to_date)}`} status="Posted ledger" icon={BarChart3} /><DataCard label="Expenses" value={formatMoney(profitLossReport.total_expenses)} meta="Posted ledger" status="Posted ledger" icon={FileCheck2} /><DataCard label="Net income" value={formatMoney(profitLossReport.net_income)} meta="Revenue less expenses" status="Derived" icon={PieChart} /><DataCard label="Accounts in report" value={String(profitLossReport.rows.length)} meta="Revenue and expense accounts" status="Derived" icon={FileBarChart} /></section> : null}
      {balanceSheetReport ? <section className="metric-grid" aria-label="Balance sheet metrics"><DataCard label="Total assets" value={formatMoney(balanceSheetReport.total_assets)} meta={`As of ${formatReportDate(balanceSheetReport.as_of)}`} status="Posted ledger" icon={Landmark} /><DataCard label="Liabilities + equity" value={formatMoney(balanceSheetReport.total_liabilities_and_equity)} meta="Control total" status="Derived" icon={PieChart} /><DataCard label="Net income" value={formatMoney(balanceSheetReport.net_income)} meta="Included in equity bridge" status="Derived" icon={BarChart3} /><DataCard label="Balance check" value={reportIsBalanced ? "Balanced" : "Review"} meta="Assets equal liabilities + equity" status={reportIsBalanced ? "Control passed" : "Control failed"} icon={reportIsBalanced ? ShieldCheck : LockKeyhole} /></section> : null}
      {generalLedgerReport ? <section className="metric-grid" aria-label="General ledger metrics"><DataCard label="Debit activity" value={formatMoney(generalLedgerReport.total_debit)} meta={`${formatReportDate(generalLedgerReport.from_date)} – ${formatReportDate(generalLedgerReport.to_date)}`} status="Posted ledger" icon={FileSpreadsheet} /><DataCard label="Credit activity" value={formatMoney(generalLedgerReport.total_credit)} meta="Posted ledger" status="Posted ledger" icon={BarChart3} /><DataCard label="Ledger lines" value={String(generalLedgerReport.rows.length)} meta="Immutable posted lines" status="Derived" icon={FileBarChart} /><DataCard label="Balance check" value={reportIsBalanced ? "Balanced" : "Review"} meta="Debit equals credit" status={reportIsBalanced ? "Control passed" : "Control failed"} icon={reportIsBalanced ? ShieldCheck : LockKeyhole} /></section> : null}
      {cashFlowReport ? <section className="metric-grid" aria-label="Cash flow metrics"><DataCard label="Opening cash" value={formatMoney(cashFlowReport.opening_cash, cashFlowReport.currency_code)} meta={`Before ${formatReportDate(cashFlowReport.from_date)}`} status="Posted ledger" icon={WalletCards} /><DataCard label="Inflows" value={formatMoney(cashFlowReport.total_inflow, cashFlowReport.currency_code)} meta="Mapped cash-account debits" status="Direct movement" icon={ArrowDownLeft} /><DataCard label="Outflows" value={formatMoney(cashFlowReport.total_outflow, cashFlowReport.currency_code)} meta="Mapped cash-account credits" status="Direct movement" icon={ArrowUpRight} /><DataCard label="Closing cash" value={formatMoney(cashFlowReport.closing_cash, cashFlowReport.currency_code)} meta={`Through ${formatReportDate(cashFlowReport.to_date)}`} status="Derived" icon={Landmark} /></section> : null}
      {cashFlowReport?.configuration_status === "configuration_required" ? <p className="form-message" role="status">Configure an active bank account mapped to the organization ledger before interpreting cash movement totals.</p> : null}
      {agedReport ? <section className="metric-grid" aria-label="Ageing metrics"><DataCard label="Outstanding" value={formatMoney(agedReport.total_outstanding)} meta={`As of ${formatReportDate(agedReport.as_of)}`} status="Posted documents" icon={Landmark} /><DataCard label="Documents" value={String(agedReport.rows.length)} meta="Open posted documents" status="Derived" icon={FileSpreadsheet} /><DataCard label="Current" value={formatMoney(agedReport.current_total)} meta="Not yet overdue" status="Due today or later" icon={ShieldCheck} /><DataCard label="Overdue" value={formatMoney(agedReport.overdue_total)} meta="Past due date" status="Review queue" icon={LockKeyhole} /></section> : null}
      {trialReport ? <div className="data-table-wrap" tabIndex={0} aria-label="Scroll trial balance table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Trial balance from {trialReport.from_date} to {trialReport.to_date}</caption><thead><tr><th scope="col">Account</th><th scope="col">Type</th><th scope="col">Debit</th><th scope="col">Credit</th><th scope="col">Balance</th></tr></thead><tbody>{visibleTrialRows.length > 0 ? visibleTrialRows.map((row) => <tr key={row.account_code}><td><strong>{row.account_code}</strong><small className="table-secondary">{row.account_name || "Unnamed account"}</small></td><td>{row.account_type || "—"}</td><td>{formatMoney(row.debit)}</td><td>{formatMoney(row.credit)}</td><td>{formatMoney(row.balance)}</td></tr>) : <tr><td className="muted-cell" colSpan={5}>{viewState === "loading" ? "Generating trial balance…" : viewState === "error" ? "Trial balance unavailable" : "No accounts match the current filter"}</td></tr>}</tbody></table></div> : null}
      {profitLossReport ? <div className="data-table-wrap" tabIndex={0} aria-label="Scroll profit and loss table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Profit and loss from {profitLossReport.from_date} to {profitLossReport.to_date}</caption><thead><tr><th scope="col">Account</th><th scope="col">Amount</th></tr></thead><tbody>{visibleProfitLossRows.length > 0 ? visibleProfitLossRows.map((row) => <tr key={row.account_code}><td><strong>{row.account_code}</strong><small className="table-secondary">{row.account_name || "Unnamed account"}</small></td><td>{formatMoney(row.amount)}</td></tr>) : <tr><td className="muted-cell" colSpan={2}>{viewState === "loading" ? "Generating profit and loss…" : viewState === "error" ? "Profit and loss unavailable" : "No revenue or expense accounts match the current filter"}</td></tr>}<tr className="table-total"><th scope="row">Net income</th><td><strong>{formatMoney(profitLossReport.net_income)}</strong></td></tr></tbody></table></div> : null}
      {balanceSheetReport ? <div className="data-table-wrap" tabIndex={0} aria-label="Scroll balance sheet table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Balance sheet as of {balanceSheetReport.as_of}</caption><thead><tr><th scope="col">Section</th><th scope="col">Account</th><th scope="col">Amount</th></tr></thead><tbody>{renderAccountRows(balanceSheetReport.assets, "Assets", normalizedSearch)}{renderAccountRows(balanceSheetReport.liabilities, "Liabilities", normalizedSearch)}{renderAccountRows(balanceSheetReport.equity, "Equity", normalizedSearch)}<tr className="table-total"><th scope="row" colSpan={2}>Total assets</th><td><strong>{formatMoney(balanceSheetReport.total_assets)}</strong></td></tr><tr className="table-total"><th scope="row" colSpan={2}>Liabilities + equity</th><td><strong>{formatMoney(balanceSheetReport.total_liabilities_and_equity)}</strong></td></tr></tbody></table></div> : null}
      {generalLedgerReport ? <div className="data-table-wrap" tabIndex={0} aria-label="Scroll general ledger table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>General ledger from {generalLedgerReport.from_date} to {generalLedgerReport.to_date}</caption><thead><tr><th scope="col">Date</th><th scope="col">Reference</th><th scope="col">Account</th><th scope="col">Memo</th><th scope="col">Source</th><th scope="col">Debit</th><th scope="col">Credit</th></tr></thead><tbody>{visibleGeneralLedgerRows.length > 0 ? visibleGeneralLedgerRows.map((row) => <tr key={`${row.entry_id}-${row.account_code}`}><td>{formatReportDate(row.journal_date)}</td><td><strong>{row.reference}</strong></td><td>{row.account_code}</td><td>{row.memo || "—"}</td><td>{row.source_type || "—"}</td><td>{formatMoney(row.debit)}</td><td>{formatMoney(row.credit)}</td></tr>) : <tr><td className="muted-cell" colSpan={7}>{viewState === "loading" ? "Generating general ledger…" : viewState === "error" ? "General ledger unavailable" : "No ledger lines match the current filter"}</td></tr>}</tbody></table></div> : null}
      {cashFlowReport ? <div className="data-table-wrap" tabIndex={0} aria-label="Scroll cash flow table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Direct mapped cash-account movement in {cashFlowReport.currency_code} from {cashFlowReport.from_date} to {cashFlowReport.to_date}</caption><thead><tr><th scope="col">Cash account</th><th scope="col">Opening</th><th scope="col">Inflows</th><th scope="col">Outflows</th><th scope="col">Net change</th><th scope="col">Closing</th></tr></thead><tbody>{visibleCashFlowRows.length > 0 ? visibleCashFlowRows.map((row) => <tr key={row.account_code}><td><strong>{row.account_code}</strong><small className="table-secondary">{row.account_name || "Unnamed account"}</small></td><td>{formatMoney(row.opening_balance, cashFlowReport.currency_code)}</td><td>{formatMoney(row.inflow, cashFlowReport.currency_code)}</td><td>{formatMoney(row.outflow, cashFlowReport.currency_code)}</td><td><strong>{formatMoney(row.net_change, cashFlowReport.currency_code)}</strong></td><td>{formatMoney(row.closing_balance, cashFlowReport.currency_code)}</td></tr>) : <tr><td className="muted-cell" colSpan={6}>{viewState === "loading" ? "Generating cash flow…" : viewState === "error" ? "Cash flow unavailable" : "No mapped cash-account movement matches the current filter"}</td></tr>}<tr className="table-total"><th scope="row">Total cash</th><td>{formatMoney(cashFlowReport.opening_cash, cashFlowReport.currency_code)}</td><td>{formatMoney(cashFlowReport.total_inflow, cashFlowReport.currency_code)}</td><td>{formatMoney(cashFlowReport.total_outflow, cashFlowReport.currency_code)}</td><td><strong>{formatMoney(cashFlowReport.net_change, cashFlowReport.currency_code)}</strong></td><td><strong>{formatMoney(cashFlowReport.closing_cash, cashFlowReport.currency_code)}</strong></td></tr></tbody></table></div> : null}
      {agedReport ? <div className="data-table-wrap" tabIndex={0} aria-label="Scroll ageing table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>{activeDefinition.label} as of {agedReport.as_of}</caption><thead><tr><th scope="col">Document</th><th scope="col">Partner</th><th scope="col">Issue date</th><th scope="col">Due date</th><th scope="col">Bucket</th><th scope="col">Total</th><th scope="col">Allocated</th><th scope="col">Outstanding</th></tr></thead><tbody>{visibleAgedRows.length > 0 ? visibleAgedRows.map((row) => <tr key={row.document_id}><td><strong>{row.document_number}</strong></td><td><code title={row.partner_id}>{shortId(row.partner_id)}</code></td><td>{formatReportDate(row.issue_date)}</td><td>{formatReportDate(row.due_date)}</td><td><StatusBadge tone={row.bucket === "current" ? "success" : "warning"}>{formatBucket(row.bucket)}</StatusBadge></td><td>{formatMoney(row.total)}</td><td>{formatMoney(row.allocated)}</td><td><strong>{formatMoney(row.outstanding)}</strong></td></tr>) : <tr><td className="muted-cell" colSpan={8}>{viewState === "loading" ? "Generating ageing report…" : viewState === "error" ? "Ageing report unavailable" : "No open documents match the current filter"}</td></tr>}<tr className="table-total"><th scope="row" colSpan={7}>Total outstanding</th><td><strong>{formatMoney(agedReport.total_outstanding)}</strong></td></tr></tbody></table></div> : null}
    </>;
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy"><p className="eyebrow">Financial intelligence</p><h1 className="page-title">Reports & insights</h1><p className="page-subtitle">Ledger-derived reporting with clear date scope, source lineage and export-ready contracts.</p></div>
        <div className="page-actions"><StatusBadge tone={headerTone}>{headerStatus}</StatusBadge>{currentReport && reportKind ? <button className="button button-secondary" type="button" onClick={() => exportReport(reportKind, currentReport)}><Download size={15} aria-hidden="true" /> Export CSV</button> : null}</div>
      </header>

      {viewState !== "ready" && viewState !== "overview" ? <section className="connection-banner" aria-labelledby="reports-connection-title" role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><ShieldCheck size={19} aria-hidden="true" /><div><strong id="reports-connection-title">{viewState === "error" ? "Report data needs attention" : "Reports stay guarded until the workspace connects"}</strong><p>{viewState === "disconnected" ? "Connect the API to generate tenant-scoped reports. No unsupported financial values are fabricated." : viewState === "unauthenticated" ? "Sign in with an organization account before generating reports." : viewState === "error" ? loadError : "Totals are derived from posted ledger lines only and remain reproducible from source records."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setReport(null); setReportKindForData(null); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry report</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}</div></section> : null}

      <nav className="report-grid" aria-label="Available financial reports">
        {reports.map(({ href, label, description, icon: Icon }) => <Link className={`report-card${activeReport === label ? " is-active" : ""}`} href={href} key={href}><span className="report-card-icon" aria-hidden="true"><Icon size={19} /></span><span><strong>{label}</strong><small>{description}</small></span><StatusBadge tone="success">Available</StatusBadge></Link>)}
      </nav>

      <section className="panel" aria-labelledby="report-preview-title">
        <div className="section-heading"><div className="section-heading-row"><div><h2 id="report-preview-title">{activeReport || "Report preview"}</h2><p>{activeDefinition ? activeDefinition.description : "Choose a report above, then set date, organization and account filters."}</p></div><StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Posted ledger only</StatusBadge></div></div>
        {reportBody}
      </section>
    </div>
  );
}
