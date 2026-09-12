"use client";

import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  FilePlus2,
  Filter,
  History,
  Link2,
  LockKeyhole,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Undo2,
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
  createJournalIdempotencyKey,
  listJournalEntries,
  postJournalEntry,
  reverseJournalEntry,
  type JournalEntry,
  type JournalLineInput,
} from "@/lib/journal";
import { formatMoney } from "@/lib/documents";

type LoadState = "idle" | "ready" | "error";
type DraftLine = JournalLineInput & { id: string };

function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Bangkok",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function currentYearStart(): string {
  return `${new Date().getFullYear()}-01-01`;
}

function currentYearEnd(): string {
  return `${new Date().getFullYear()}-12-31`;
}

function emptyLine(): DraftLine {
  let id = globalThis.crypto?.randomUUID?.();
  if (!id && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    id = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!id) {
    throw new Error("Secure randomness is unavailable");
  }
  return { id, account_code: "", debit: "0", credit: "0", memo: "" };
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function safeError(error: unknown, action: "load" | "post" | "reverse"): string {
  if (error instanceof ApiConfigurationError) return "Connect the API endpoint before using the journal workspace.";
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Sign in again to continue.";
    if (error.status === 403) return `Your role cannot ${action} journal entries in this organization.`;
    if (error.status === 409) return action === "reverse" ? "This journal entry cannot be reversed under the current ledger controls." : "The journal entry conflicts with the current period or account controls.";
  }
  return action === "load" ? "Live journal data is unavailable. Retry the request or review the API connection." : `The journal entry could not be ${action === "reverse" ? "reversed" : "posted"}. Review the controls and try again.`;
}

export function JournalWorkbench() {
  const configuredEndpoint = useSyncExternalStore(subscribeToApiBaseUrl, getApiBaseUrl, getServerApiBaseUrl);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [reference, setReference] = useState("");
  const [fromDate, setFromDate] = useState(currentYearStart);
  const [toDate, setToDate] = useState(currentYearEnd);
  const [draftReference, setDraftReference] = useState("");
  const [draftFromDate, setDraftFromDate] = useState(currentYearStart);
  const [draftToDate, setDraftToDate] = useState(currentYearEnd);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reversingId, setReversingId] = useState<string | null>(null);
  const [isPosting, setIsPosting] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([emptyLine(), emptyLine()]);
  const [lineError, setLineError] = useState("");

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;
  const visibleEntries = viewState === "disconnected" || viewState === "unauthenticated" ? [] : entries;
  const postedTotal = visibleEntries.reduce((sum, entry) => sum + Number(entry.total_debit), 0);
  const reversedCount = visibleEntries.filter((entry) => entry.reversal_of_id).length;

  useEffect(() => {
    const controller = new AbortController();
    if (!configuredEndpoint || !getAccessToken()) return () => controller.abort();
    listJournalEntries({ reference, fromDate, toDate, limit: 50, offset: 0 }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setEntries(result.items);
          setTotal(result.total);
          setNextOffset(result.next_offset);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(safeError(error, "load"));
          setLoadState("error");
        }
      });
    return () => controller.abort();
  }, [configuredEndpoint, fromDate, refreshNonce, reference, toDate]);

  const handleFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draftFromDate > draftToDate) {
      setActionError("The start date must be on or before the end date.");
      return;
    }
    setActionError("");
    setEntries([]);
    setLoadState("idle");
    setReference(draftReference.trim());
    setFromDate(draftFromDate);
    setToDate(draftToDate);
  };

  const updateLine = (id: string, field: keyof JournalLineInput, value: string) => {
    setLines((current) => current.map((line) => line.id === id ? { ...line, [field]: value } : line));
    setLineError("");
  };

  const validateLines = (): JournalLineInput[] | null => {
    const prepared = lines.map(({ id: _id, ...line }) => ({ ...line, account_code: line.account_code.trim(), debit: line.debit || "0", credit: line.credit || "0", memo: line.memo?.trim() || undefined }));
    if (prepared.length < 2 || prepared.some((line) => !line.account_code)) {
      setLineError("Add at least two lines and provide an account code for each line.");
      return null;
    }
    if (prepared.some((line) => Number(line.debit) > 0 && Number(line.credit) > 0)) {
      setLineError("Each journal line must contain either a debit or a credit, never both.");
      return null;
    }
    if (prepared.some((line) => Number(line.debit) <= 0 && Number(line.credit) <= 0)) {
      setLineError("Each journal line must contain a positive debit or credit amount.");
      return null;
    }
    const debit = prepared.reduce((sum, line) => sum + Number(line.debit), 0);
    const credit = prepared.reduce((sum, line) => sum + Number(line.credit), 0);
    if (!Number.isFinite(debit) || !Number.isFinite(credit) || Math.abs(debit - credit) > 0.005) {
      setLineError("Journal lines must balance before posting.");
      return null;
    }
    return prepared;
  };

  const handlePost = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const preparedLines = validateLines();
    if (!preparedLines) return;
    const data = new FormData(event.currentTarget);
    setIsPosting(true);
    try {
      await postJournalEntry({
        reference: String(data.get("reference") || "").trim(),
        memo: String(data.get("memo") || "").trim() || undefined,
        journal_date: String(data.get("journal_date") || ""),
        source_type: String(data.get("source_type") || "").trim(),
        lines: preparedLines,
      }, createJournalIdempotencyKey("post"));
      setIsCreateOpen(false);
      setNotice("Journal entry posted");
      setLines([emptyLine(), emptyLine()]);
      setLoadState("idle");
      setRefreshNonce((value) => value + 1);
    } catch (error: unknown) {
      setActionError(safeError(error, "post"));
    } finally {
      setIsPosting(false);
    }
  };

  const handleReverse = async (entry: JournalEntry) => {
    setActionError("");
    setReversingId(entry.id);
    try {
      await reverseJournalEntry(
        entry.id,
        createJournalIdempotencyKey("reverse"),
        todayIso(),
      );
      setNotice("Journal entry reversed");
      setLoadState("idle");
      setRefreshNonce((value) => value + 1);
    } catch (error: unknown) {
      setActionError(safeError(error, "reverse"));
    } finally {
      setReversingId(null);
    }
  };

  const handleLoadMore = async () => {
    if (nextOffset === null) return;
    try {
      const result = await listJournalEntries({ reference, fromDate, toDate, limit: 50, offset: nextOffset });
      setEntries((current) => [...current, ...result.items]);
      setTotal(result.total);
      setNextOffset(result.next_offset);
    } catch (error: unknown) {
      setLoadError(safeError(error, "load"));
    }
  };

  const statusLabel = { idle: "Loading workspace", loading: "Loading live journal", ready: `${total} posted entr${total === 1 ? "y" : "ies"}`, disconnected: "API not connected", unauthenticated: "Sign-in required", error: "Journal unavailable" }[viewState];
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";
  const canCreate = canUseWorkspace && viewState === "ready";

  return (
    <div className="page-stack">
      <header className="page-header"><div className="page-header-copy"><p className="eyebrow">Core ledger</p><h1 className="page-title">Accounting workspace</h1><p className="page-subtitle">Post, review and reverse double-entry activity with clear period and approval controls.</p></div><div className="page-actions"><StatusBadge tone={statusTone}>{statusLabel}</StatusBadge><button className="button button-primary" type="button" disabled={!canCreate} onClick={() => { setActionError(""); setLineError(""); setIsCreateOpen(true); }}><FilePlus2 size={15} aria-hidden="true" /> New journal entry</button></div></header>

      <nav className="tab-list" aria-label="Accounting sections"><a href="/accounting" aria-current="page">Journal</a><a href="/accounting/chart-of-accounts">Chart of accounts</a><a href="/accounting/periods">Fiscal periods</a><a href="/accounting/reconciliation">Reconciliation</a></nav>

      {viewState !== "ready" ? <section className="connection-banner" aria-labelledby="journal-connection-title" role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><Link2 size={19} aria-hidden="true" /><div><strong id="journal-connection-title">{viewState === "error" ? "Journal data needs attention" : "Posting stays guarded until the workspace connects"}</strong><p>{viewState === "disconnected" ? "Connect the API to load organization data. No financial values are fabricated in this interface." : viewState === "unauthenticated" ? "Sign in with an organization account before reading or changing ledger activity." : viewState === "error" ? loadError : "Entries are validated for balance, fiscal period status, account activity, idempotency and audit lineage on the server."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setEntries([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry journal load</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}</div></section> : null}
      {notice ? <p className="form-message" role="status" aria-live="polite">{notice}</p> : null}
      {actionError ? <p className="form-message" role="alert">{actionError}</p> : null}

      {isCreateOpen ? <section className="panel" aria-labelledby="journal-create-title"><div className="section-heading-row"><div className="section-heading"><h2 id="journal-create-title">New journal entry</h2><p>Posting is immutable. Corrections use a separate reversal entry.</p></div><button className="icon-button" type="button" aria-label="Close journal entry form" onClick={() => setIsCreateOpen(false)}><X size={17} aria-hidden="true" /></button></div><form className="form-grid" onSubmit={handlePost}><div className="panel-grid two-column"><div className="field"><label htmlFor="journal-reference">Reference</label><input id="journal-reference" name="reference" required maxLength={100} placeholder="MANUAL-0001" /></div><div className="field"><label htmlFor="journal-date">Journal date</label><input id="journal-date" name="journal_date" type="date" required defaultValue={todayIso()} /></div><div className="field"><label htmlFor="journal-source-type">Source type</label><input id="journal-source-type" name="source_type" required maxLength={100} defaultValue="manual" /></div><div className="field"><label htmlFor="journal-memo">Memo</label><input id="journal-memo" name="memo" maxLength={500} placeholder="Describe the business reason" /></div></div><div className="section-heading-row"><div className="section-heading"><h3>Journal lines</h3><p>Use one side per line. Totals must balance exactly.</p></div><button className="button button-secondary" type="button" onClick={() => setLines((current) => [...current, emptyLine()])}><Plus size={15} aria-hidden="true" /> Add line</button></div><div className="journal-line-list">{lines.map((line, index) => <div className="journal-line" key={line.id}><div className="field"><label htmlFor={`journal-line-${index}-account`}>Line {index + 1} account</label><input id={`journal-line-${index}-account`} value={line.account_code} onChange={(event) => updateLine(line.id, "account_code", event.target.value)} required placeholder="1001" /></div><div className="field"><label htmlFor={`journal-line-${index}-debit`}>Line {index + 1} debit</label><input id={`journal-line-${index}-debit`} type="number" min="0" step="0.01" value={line.debit} onChange={(event) => updateLine(line.id, "debit", event.target.value)} /></div><div className="field"><label htmlFor={`journal-line-${index}-credit`}>Line {index + 1} credit</label><input id={`journal-line-${index}-credit`} type="number" min="0" step="0.01" value={line.credit} onChange={(event) => updateLine(line.id, "credit", event.target.value)} /></div><div className="field"><label htmlFor={`journal-line-${index}-memo`}>Line {index + 1} memo</label><input id={`journal-line-${index}-memo`} value={line.memo || ""} onChange={(event) => updateLine(line.id, "memo", event.target.value)} placeholder="Optional" /></div>{lines.length > 2 ? <button className="icon-button" type="button" aria-label={`Remove line ${index + 1}`} onClick={() => setLines((current) => current.filter((item) => item.id !== line.id))}><X size={16} aria-hidden="true" /></button> : null}</div>)}</div>{lineError ? <p className="form-message" role="alert">{lineError}</p> : null}<div className="page-actions"><button className="button button-primary" type="submit" disabled={isPosting} aria-busy={isPosting}><Send size={15} aria-hidden="true" /> {isPosting ? "Posting…" : "Post journal entry"}</button><button className="button button-secondary" type="button" onClick={() => setIsCreateOpen(false)}>Cancel</button></div></form></section> : null}

      <section className="metric-grid" aria-label="Journal metrics"><DataCard label="Posted entries" value={viewState === "ready" ? String(total) : "—"} meta="Server-counted date scope" status={viewState === "ready" ? "Posted only" : "Awaiting API"} icon={BookOpen} /><DataCard label="Posted value" value={viewState === "ready" ? formatMoney(postedTotal.toFixed(2)) : "—"} meta="Debit side in current page" status={viewState === "ready" ? "Balanced source" : "Not evaluated"} icon={CheckCircle2} /><DataCard label="Reversals" value={viewState === "ready" ? String(reversedCount) : "—"} meta="Correction entries loaded" status={viewState === "ready" ? "Auditable" : "Awaiting API"} icon={Undo2} /><DataCard label="Posting control" value="Active" meta="Balance, period and account policy" status="Server enforced" icon={ShieldCheck} /></section>

      <section className="panel" aria-label="Journal entry register" aria-labelledby="journal-register-title"><div className="section-heading"><div className="section-heading-row"><div><h2 id="journal-register-title">Journal entries</h2><p>Every posted entry remains immutable and traceable to its source and audit event.</p></div><StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Immutable</StatusBadge></div></div><form className="workbench-toolbar" aria-label="Journal filters" onSubmit={handleFilters}><label className="search-trigger workbench-search" htmlFor="journal-reference-filter"><Search size={16} aria-hidden="true" /><span className="visually-hidden">Reference filter</span><input id="journal-reference-filter" type="search" value={draftReference} onChange={(event) => setDraftReference(event.target.value)} placeholder="Search reference" disabled={!canUseWorkspace || viewState === "loading"} /></label><label className="field-inline" htmlFor="journal-from-date"><span>From</span><input id="journal-from-date" type="date" value={draftFromDate} onChange={(event) => setDraftFromDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label><label className="field-inline" htmlFor="journal-to-date"><span>To</span><input id="journal-to-date" type="date" value={draftToDate} onChange={(event) => setDraftToDate(event.target.value)} disabled={!canUseWorkspace || viewState === "loading"} /></label><button className="button button-secondary" type="submit" disabled={!canUseWorkspace || viewState === "loading"}><Filter size={15} aria-hidden="true" /> Apply filters</button></form><div className="data-table-wrap" tabIndex={0} aria-label="Scroll journal entry table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Posted journal entries</caption><thead><tr><th scope="col">Reference</th><th scope="col">Journal date</th><th scope="col">Source</th><th scope="col">Debit</th><th scope="col">Credit</th><th scope="col">Posted at</th><th scope="col">Controls</th></tr></thead><tbody>{visibleEntries.length > 0 ? visibleEntries.map((entry) => <tr key={entry.id}><td><strong>{entry.reference}</strong><small className="table-secondary">{entry.memo || `${entry.lines.length} lines`}</small></td><td>{formatDate(entry.journal_date)}</td><td>{entry.source_type || "—"}</td><td>{formatMoney(entry.total_debit)}</td><td>{formatMoney(entry.total_credit)}</td><td>{formatDateTime(entry.posted_at)}</td><td><div className="page-actions"><button className="button button-ghost" type="button" onClick={() => setExpandedId((current) => current === entry.id ? null : entry.id)}>{expandedId === entry.id ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />} {expandedId === entry.id ? "Hide lines" : "View lines"}</button>{!entry.reversal_of_id ? <button className="button button-ghost" type="button" aria-label={`Reverse ${entry.reference}`} disabled={reversingId === entry.id} onClick={() => handleReverse(entry)}><Undo2 size={14} aria-hidden="true" /> {reversingId === entry.id ? "Reversing…" : "Reverse"}</button> : <StatusBadge tone="neutral">Reversal</StatusBadge>}</div></td></tr>) : <tr><td className="muted-cell" colSpan={7}>{viewState === "loading" ? "Loading journal entries…" : viewState === "error" ? "Journal entries unavailable" : viewState === "ready" ? "No journal entries in this scope" : "No connected journal entries"}</td></tr>}</tbody></table></div>{expandedId ? <div className="journal-detail" aria-label="Journal line detail">{(() => { const entry = visibleEntries.find((item) => item.id === expandedId); return entry ? <><div className="section-heading"><h3>{entry.reference} lines</h3><p>{entry.lines.length} immutable ledger lines</p></div><div className="data-table-wrap"><table className="data-table"><caption>Lines for {entry.reference}</caption><thead><tr><th scope="col">Line</th><th scope="col">Account</th><th scope="col">Memo</th><th scope="col">Debit</th><th scope="col">Credit</th></tr></thead><tbody>{entry.lines.map((line) => <tr key={line.id}><td>{line.line_no}</td><td>{line.account_code}</td><td>{line.memo || "—"}</td><td>{formatMoney(line.debit)}</td><td>{formatMoney(line.credit)}</td></tr>)}</tbody></table></div></> : null; })()}</div> : null}{viewState === "ready" && visibleEntries.length === 0 ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><History size={20} /></span><strong>No journal activity to display</strong><p>Choose a connected organization and date scope to review posted ledger activity.</p><StatusBadge tone="info"><CircleHelp size={12} aria-hidden="true" /> Register ready</StatusBadge></div> : null}{viewState === "ready" && nextOffset !== null ? <div className="page-actions"><button className="button button-secondary" type="button" onClick={handleLoadMore}>Load more entries</button><span className="page-subtitle">Showing {visibleEntries.length} of {total}</span></div> : null}</section>
    </div>
  );
}
