"use client";

import {
  BookOpenCheck,
  CalendarCheck2,
  CalendarClock,
  CircleHelp,
  FileClock,
  Landmark,
  LockKeyhole,
  Pencil,
  Plus,
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
  createAccountingIdempotencyKey,
  createChartAccount,
  createFiscalPeriod,
  listChartAccounts,
  listFiscalPeriods,
  lockFiscalPeriod,
  updateChartAccount,
  type AccountType,
  type ChartAccount,
  type FiscalPeriod,
} from "@/lib/accounting";

type AccountingSurface = "accounts" | "periods" | "reconciliation";
type LoadState = "idle" | "ready" | "error";

const content = {
  accounts: {
    eyebrow: "Accounting master data",
    title: "Chart of accounts",
    subtitle: "Manage a structured account hierarchy with clear posting boundaries and an audit-safe change history.",
    tab: "Chart of accounts",
    icon: BookOpenCheck,
    emptyTitle: "Chart of accounts is empty",
    emptyDescription: "Create the first account after confirming the organization and posting policy.",
  },
  periods: {
    eyebrow: "Close management",
    title: "Fiscal periods",
    subtitle: "Open, review and lock accounting periods with explicit close controls and immutable posting boundaries.",
    tab: "Fiscal periods",
    icon: CalendarCheck2,
    emptyTitle: "No fiscal periods connected",
    emptyDescription: "Create a period before posting journals or running controlled close procedures.",
  },
  reconciliation: {
    eyebrow: "Cash controls",
    title: "Reconciliation workspace",
    subtitle: "Prepare bank and cash reconciliation with evidence-led matching and no silent ledger changes.",
    tab: "Reconciliation",
    icon: Landmark,
    emptyTitle: "Reconciliation is managed in Banking",
    emptyDescription: "Use the banking control surface to import statements, match payments and commit reconciliation evidence.",
  },
} as const;

const accountTypes: Array<{ value: AccountType; label: string }> = [
  { value: "asset", label: "Asset" },
  { value: "liability", label: "Liability" },
  { value: "equity", label: "Equity" },
  { value: "revenue", label: "Revenue" },
  { value: "expense", label: "Expense" },
];

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Bangkok",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function safeError(error: unknown, action: "load" | "create" | "update" | "lock", noun: string): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before using live accounting controls.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (error.status === 403) {
      return `Your role cannot ${action} ${noun} records in this organization.`;
    }
    if (error.status === 409) {
      return action === "lock"
        ? "The fiscal period cannot be locked under the current posting controls. Reload and review its status."
        : `The ${noun} conflicts with current organization controls.`;
    }
  }
  return action === "load"
    ? `Live ${noun} data is unavailable. Retry the request or review the API connection.`
    : `The ${noun} could not be ${action === "lock" ? "locked" : action === "update" ? "updated" : "created"}. Review the fields and try again.`;
}

function statusTone(viewState: LoadState | "loading" | "disconnected" | "unauthenticated"): "neutral" | "success" | "warning" | "danger" | "info" {
  if (viewState === "ready") {
    return "success";
  }
  if (viewState === "error" || viewState === "unauthenticated") {
    return "danger";
  }
  if (viewState === "loading") {
    return "info";
  }
  return "warning";
}

export function AccountingWorkbench({ surface }: Readonly<{ surface: AccountingSurface }>) {
  const page = content[surface];
  const Icon = page.icon;
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [accounts, setAccounts] = useState<ChartAccount[]>([]);
  const [periods, setPeriods] = useState<FiscalPeriod[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [search, setSearch] = useState("");
  const [accountType, setAccountType] = useState<AccountType | "">("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<ChartAccount | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [lockingPeriodId, setLockingPeriodId] = useState<string | null>(null);

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
    if (!configuredEndpoint || !getAccessToken() || surface === "reconciliation") {
      return () => controller.abort();
    }

    const request = surface === "accounts"
      ? listChartAccounts(controller.signal).then((result) => {
          if (!controller.signal.aborted) {
            setAccounts(result);
          }
        })
      : listFiscalPeriods(controller.signal).then((result) => {
          if (!controller.signal.aborted) {
            setPeriods(result);
          }
        });

    request
      .then(() => {
        if (!controller.signal.aborted) {
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(safeError(error, "load", surface === "accounts" ? "chart of accounts" : "fiscal period"));
          setLoadState("error");
        }
      });

    return () => controller.abort();
  }, [configuredEndpoint, refreshNonce, surface]);

  const visibleAccounts = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return accounts.filter((account) => {
      const matchesSearch = !normalized || `${account.code} ${account.name}`.toLowerCase().includes(normalized);
      const matchesType = !accountType || account.account_type === accountType;
      return matchesSearch && matchesType;
    });
  }, [accounts, accountType, search]);
  const visiblePeriods = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return periods.filter((period) => !normalized || `${period.name} ${period.start_date} ${period.end_date} ${period.status}`.toLowerCase().includes(normalized));
  }, [periods, search]);

  const handleCreateAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    const parentId = String(data.get("parent_id") || "").trim();
    setIsCreating(true);
    try {
      const created = await createChartAccount(
        {
          code: String(data.get("code") || "").trim(),
          name: String(data.get("name") || "").trim(),
          account_type: String(data.get("account_type") || "asset") as AccountType,
          parent_id: parentId || undefined,
          is_control: data.get("is_control") === "on",
          is_cash_equivalent: data.get("is_cash_equivalent") === "on",
        },
        createAccountingIdempotencyKey("account-create"),
      );
      setAccounts((current) => [...current, created].sort((left, right) => left.code.localeCompare(right.code)));
      setIsCreateOpen(false);
      setNotice("Account created");
    } catch (error: unknown) {
      setActionError(safeError(error, "create", "account"));
    } finally {
      setIsCreating(false);
    }
  };

  const handleUpdateAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingAccount) {
      return;
    }
    setActionError("");
    const data = new FormData(event.currentTarget);
    setIsUpdating(true);
    try {
      const parentId = String(data.get("parent_id") || "").trim();
      const updated = await updateChartAccount(
        editingAccount.id,
        {
          expected_version: editingAccount.version,
          name: String(data.get("name") || "").trim(),
          parent_id: parentId || null,
          is_control: data.get("is_control") === "on",
          is_cash_equivalent: data.get("is_cash_equivalent") === "on",
          is_active: data.get("is_active") === "on",
        },
        createAccountingIdempotencyKey("account-update"),
      );
      setAccounts((current) => current.map((account) => account.id === updated.id ? updated : account));
      setEditingAccount(null);
      setNotice("Account updated");
    } catch (error: unknown) {
      setActionError(safeError(error, "update", "account"));
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCreatePeriod = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    setIsCreating(true);
    try {
      const created = await createFiscalPeriod(
        {
          name: String(data.get("name") || "").trim(),
          start_date: String(data.get("start_date") || ""),
          end_date: String(data.get("end_date") || ""),
        },
        createAccountingIdempotencyKey("period-create"),
      );
      setPeriods((current) => [created, ...current].sort((left, right) => right.start_date.localeCompare(left.start_date)));
      setIsCreateOpen(false);
      setNotice("Fiscal period created");
    } catch (error: unknown) {
      setActionError(safeError(error, "create", "fiscal period"));
    } finally {
      setIsCreating(false);
    }
  };

  const handleLockPeriod = async (period: FiscalPeriod) => {
    setActionError("");
    setLockingPeriodId(period.id);
    try {
      const locked = await lockFiscalPeriod(period.id, createAccountingIdempotencyKey("period-lock"));
      setPeriods((current) => current.map((item) => item.id === locked.id ? locked : item));
      setNotice("Fiscal period locked");
    } catch (error: unknown) {
      setActionError(safeError(error, "lock", "fiscal period"));
    } finally {
      setLockingPeriodId(null);
    }
  };

  const activeAccounts = accounts.filter((account) => account.is_active).length;
  const controlAccounts = accounts.filter((account) => account.is_control).length;
  const cashEquivalentAccounts = accounts.filter(
    (account) => account.is_active && account.is_cash_equivalent,
  ).length;
  const openPeriods = periods.filter((period) => period.status === "open").length;
  const lockedPeriods = periods.filter((period) => period.status === "locked").length;
  const statusLabel = {
    idle: "Loading workspace",
    loading: "Loading live data",
    ready: surface === "accounts" ? `${accounts.length} live account${accounts.length === 1 ? "" : "s"}` : surface === "periods" ? `${periods.length} live period${periods.length === 1 ? "" : "s"}` : "Banking control surface",
    disconnected: "API not connected",
    unauthenticated: "Sign-in required",
    error: "Data unavailable",
  }[viewState];

  const registerLabel = surface === "accounts" ? "Chart of accounts register" : "Fiscal periods register";
  const canCreate = canUseWorkspace && viewState === "ready" && surface !== "reconciliation";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">{page.eyebrow}</p>
          <h1 className="page-title">{page.title}</h1>
          <p className="page-subtitle">{page.subtitle}</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone={statusTone(viewState)}>{statusLabel}</StatusBadge>
          {surface === "reconciliation" ? (
            <Link className="button button-primary" href="/banking"><Landmark size={15} aria-hidden="true" /> Open banking controls</Link>
          ) : (
            <button className="button button-primary" type="button" disabled={!canCreate} onClick={() => { setActionError(""); setIsCreateOpen(true); }}>
              <Plus size={15} aria-hidden="true" /> {surface === "accounts" ? "Add account" : "Open period"}
            </button>
          )}
        </div>
      </header>

      <nav className="tab-list" aria-label="Accounting administration sections">
        <Link href="/accounting">Journal</Link>
        <Link href="/accounting/chart-of-accounts" aria-current={surface === "accounts" ? "page" : undefined}>Chart of accounts</Link>
        <Link href="/accounting/periods" aria-current={surface === "periods" ? "page" : undefined}>Fiscal periods</Link>
        <Link href="/accounting/reconciliation" aria-current={surface === "reconciliation" ? "page" : undefined}>Reconciliation</Link>
      </nav>

      {surface === "reconciliation" ? (
        <>
          <section className="connection-banner" aria-labelledby="reconciliation-handoff-title">
            <div className="connection-banner-copy">
              <Landmark size={19} aria-hidden="true" />
              <div>
                <strong id="reconciliation-handoff-title">Reconciliation is a banking control, not a journal shortcut</strong>
                <p>Import batches, immutable bank movements and posted-payment matching are managed together in the banking workspace.</p>
              </div>
            </div>
            <Link className="button button-secondary" href="/banking">Go to Banking & reconciliation</Link>
          </section>
          <section className="panel"><div className="empty-state"><span className="empty-state-icon" aria-hidden="true"><CalendarClock size={20} /></span><strong>{page.emptyTitle}</strong><p>{page.emptyDescription}</p><Link className="button button-secondary" href="/banking">Open reconciliation controls</Link></div></section>
        </>
      ) : viewState !== "ready" ? (
        <section className="connection-banner" aria-labelledby={`${surface}-connection-title`} role={viewState === "error" ? "alert" : undefined}>
          <div className="connection-banner-copy">
            <ShieldCheck size={19} aria-hidden="true" />
            <div>
              <strong id={`${surface}-connection-title`}>{viewState === "error" ? `${page.title} data needs attention` : "Accounting controls stay guarded until the workspace connects"}</strong>
              <p>{viewState === "disconnected" ? "Connect the API to load organization data. No financial values are fabricated in this interface." : viewState === "unauthenticated" ? "Sign in with an organization account before reading or changing accounting controls." : viewState === "error" ? loadError : "Every mutation is organization-scoped, idempotent and audited by the server."}</p>
            </div>
          </div>
          <div className="page-actions">
            {viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setAccounts([]); setPeriods([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry accounting load</button> : null}
            {viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}
          </div>
        </section>
      ) : null}

      {notice ? <p className="form-message" role="status" aria-live="polite">{notice}</p> : null}
      {actionError ? <p className="form-message" role="alert">{actionError}</p> : null}

      {isCreateOpen && surface === "accounts" ? (
        <section className="panel" aria-labelledby="create-account-title">
          <div className="section-heading-row"><div className="section-heading"><h2 id="create-account-title">Add account</h2><p>Create an active account in the authorized organization. Posting boundaries are enforced server-side.</p></div><button className="icon-button" type="button" aria-label="Close create account form" onClick={() => setIsCreateOpen(false)}><X size={17} aria-hidden="true" /></button></div>
          <form className="form-grid" onSubmit={handleCreateAccount}>
            <div className="panel-grid two-column">
              <div className="field"><label htmlFor="account-code">Account code</label><input id="account-code" name="code" required maxLength={32} pattern="[A-Za-z0-9._/-]+" placeholder="4000" /></div>
              <div className="field"><label htmlFor="account-name">Account name</label><input id="account-name" name="name" required maxLength={200} placeholder="Revenue" /></div>
              <div className="field"><label htmlFor="account-type">Account type</label><select id="account-type" name="account_type" required defaultValue="asset">{accountTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></div>
              <div className="field"><label htmlFor="account-parent">Parent account</label><select id="account-parent" name="parent_id" defaultValue=""><option value="">No parent</option>{accounts.filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></div>
            </div>
            <div className="panel-grid two-column">
              <label className="checkbox-field"><input type="checkbox" name="is_control" /> <span>Control account <small>Control accounts cannot receive direct journal postings.</small></span></label>
              <label className="checkbox-field"><input type="checkbox" name="is_cash_equivalent" /> <span>Cash equivalent <small>Include this non-control asset account in cash-flow reporting.</small></span></label>
            </div>
            <div className="page-actions"><button className="button button-primary" type="submit" disabled={isCreating} aria-busy={isCreating}><Plus size={15} aria-hidden="true" /> {isCreating ? "Creating…" : "Create account"}</button><button className="button button-secondary" type="button" onClick={() => setIsCreateOpen(false)}>Cancel</button></div>
          </form>
        </section>
      ) : null}

      {editingAccount ? (
        <section className="panel" aria-labelledby="edit-account-title">
          <div className="section-heading-row"><div className="section-heading"><h2 id="edit-account-title">Edit {editingAccount.code}</h2><p>Account code and type remain immutable. Changes use optimistic version control.</p></div><button className="icon-button" type="button" aria-label="Close edit account form" onClick={() => setEditingAccount(null)}><X size={17} aria-hidden="true" /></button></div>
          <form className="form-grid" onSubmit={handleUpdateAccount}>
            <div className="panel-grid two-column"><div className="field"><label htmlFor="edit-account-name">Account name</label><input id="edit-account-name" name="name" required defaultValue={editingAccount.name} /></div><div className="field"><label htmlFor="edit-account-parent">Parent account</label><select id="edit-account-parent" name="parent_id" defaultValue={editingAccount.parent_id || ""}><option value="">No parent</option>{accounts.filter((account) => account.is_active && account.id !== editingAccount.id).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></div></div>
            <div className="panel-grid two-column"><label className="checkbox-field"><input type="checkbox" name="is_control" defaultChecked={editingAccount.is_control} /> <span>Control account</span></label><label className="checkbox-field"><input type="checkbox" name="is_cash_equivalent" defaultChecked={editingAccount.is_cash_equivalent} /> <span>Cash equivalent</span></label><label className="checkbox-field"><input type="checkbox" name="is_active" defaultChecked={editingAccount.is_active} /> <span>Active account</span></label></div>
            <div className="page-actions"><button className="button button-primary" type="submit" disabled={isUpdating} aria-busy={isUpdating}><Pencil size={15} aria-hidden="true" /> {isUpdating ? "Saving…" : "Save account"}</button><button className="button button-secondary" type="button" onClick={() => setEditingAccount(null)}>Cancel</button></div>
          </form>
        </section>
      ) : null}

      {isCreateOpen && surface === "periods" ? (
        <section className="panel" aria-labelledby="create-period-title">
          <div className="section-heading-row"><div className="section-heading"><h2 id="create-period-title">Open fiscal period</h2><p>Period dates define the posting boundary. A locked period cannot accept new journal entries.</p></div><button className="icon-button" type="button" aria-label="Close create fiscal period form" onClick={() => setIsCreateOpen(false)}><X size={17} aria-hidden="true" /></button></div>
          <form className="form-grid" onSubmit={handleCreatePeriod}>
            <div className="panel-grid two-column"><div className="field"><label htmlFor="period-name">Period name</label><input id="period-name" name="name" required placeholder="FY2026" /></div><div className="field"><label htmlFor="period-start">Start date</label><input id="period-start" name="start_date" type="date" required defaultValue={`${todayIso().slice(0, 4)}-01-01`} /></div><div className="field"><label htmlFor="period-end">End date</label><input id="period-end" name="end_date" type="date" required defaultValue={`${todayIso().slice(0, 4)}-12-31`} /></div></div>
            <div className="page-actions"><button className="button button-primary" type="submit" disabled={isCreating} aria-busy={isCreating}><Plus size={15} aria-hidden="true" /> {isCreating ? "Opening…" : "Open period"}</button><button className="button button-secondary" type="button" onClick={() => setIsCreateOpen(false)}>Cancel</button></div>
          </form>
        </section>
      ) : null}

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        <DataCard label={surface === "accounts" ? "Active accounts" : "Open periods"} value={viewState === "ready" ? String(surface === "accounts" ? activeAccounts : openPeriods) : "—"} meta="Live organization records" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={Icon} />
        <DataCard label={surface === "accounts" ? "Control accounts" : "Locked periods"} value={viewState === "ready" ? String(surface === "accounts" ? controlAccounts : lockedPeriods) : "—"} meta={surface === "accounts" ? "Direct posting blocked" : "Close boundary enforced"} status={viewState === "ready" ? "Evaluated" : "Not evaluated"} icon={ShieldCheck} />
        <DataCard label={surface === "accounts" ? "Cash equivalents" : "Last activity"} value={viewState === "ready" && surface === "accounts" ? String(cashEquivalentAccounts) : "—"} meta={surface === "accounts" ? "Included in cash-flow mapping" : "Audit timestamp"} status={viewState === "ready" ? surface === "accounts" ? "Mapped" : "Use Audit" : "Awaiting API"} icon={FileClock} />
        <DataCard label="Control health" value={viewState === "ready" ? "Ready" : "—"} meta="Policy checks" status={viewState === "ready" ? "Server enforced" : "Not evaluated"} icon={LockKeyhole} />
      </section>

      <section className="panel" aria-label={registerLabel} aria-labelledby={`${surface}-register-title`}>
        <div className="section-heading"><div className="section-heading-row"><div><h2 id={`${surface}-register-title`}>{page.tab} register</h2><p>All records are read within the signed-in tenant and organization boundary.</p></div><StatusBadge tone="info"><ShieldCheck size={12} aria-hidden="true" /> Tenant scoped</StatusBadge></div></div>
        <div className="workbench-toolbar">
          <label className="search-trigger workbench-search" htmlFor={`${surface}-search`}><Search size={16} aria-hidden="true" /><span className="visually-hidden">Search {page.tab}</span><input id={`${surface}-search`} type="search" placeholder={`Search ${page.tab.toLowerCase()}`} value={search} onChange={(event) => setSearch(event.target.value)} disabled={!canUseWorkspace || viewState !== "ready"} /></label>
          {surface === "accounts" ? <label className="field-inline" htmlFor="account-type-filter"><span className="visually-hidden">Filter account type</span><select id="account-type-filter" value={accountType} onChange={(event) => setAccountType(event.target.value as AccountType | "")} disabled={!canUseWorkspace || viewState !== "ready"}><option value="">All types</option>{accountTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label> : null}
          <button className="button button-secondary" type="button" disabled={!canUseWorkspace || viewState === "loading"} onClick={() => { setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Refresh</button>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label={`Scroll ${page.tab} table horizontally`} aria-busy={viewState === "loading"}>
          <table className="data-table"><caption>{page.tab} register</caption>
            {surface === "accounts" ? <><thead><tr><th scope="col">Code</th><th scope="col">Account name</th><th scope="col">Type</th><th scope="col">Posting</th><th scope="col">Version</th><th scope="col">Controls</th></tr></thead><tbody>{visibleAccounts.length > 0 ? visibleAccounts.map((account) => <tr key={account.id}><td><strong>{account.code}</strong></td><td>{account.name}<small className="table-secondary">{account.parent_id ? `Child of ${accounts.find((parent) => parent.id === account.parent_id)?.code || "account"}` : "Top level"}</small></td><td><StatusBadge tone="info">{account.account_type}</StatusBadge></td><td>{account.is_control ? <StatusBadge tone="warning">Control</StatusBadge> : account.is_active ? <><StatusBadge tone="success">Postable</StatusBadge>{account.is_cash_equivalent ? <StatusBadge tone="info">Cash equivalent</StatusBadge> : null}</> : <StatusBadge tone="neutral">Inactive</StatusBadge>}</td><td>{account.version}</td><td><button className="button button-ghost" type="button" aria-label={`Edit ${account.code}`} onClick={() => { setActionError(""); setEditingAccount(account); }}><Pencil size={14} aria-hidden="true" /> Edit</button></td></tr>) : <tr><td className="muted-cell" colSpan={6}>{viewState === "loading" ? "Loading accounts…" : viewState === "error" ? "Accounts unavailable" : viewState === "ready" ? "No accounts match the current filters" : "No connected accounts"}</td></tr>}</tbody></> : <><thead><tr><th scope="col">Period</th><th scope="col">Date range</th><th scope="col">Status</th><th scope="col">Version</th><th scope="col">Locked at</th><th scope="col">Controls</th></tr></thead><tbody>{visiblePeriods.length > 0 ? visiblePeriods.map((period) => <tr key={period.id}><td><strong>{period.name}</strong></td><td>{formatDate(period.start_date)} – {formatDate(period.end_date)}</td><td>{period.status === "open" ? <StatusBadge tone="success">Open</StatusBadge> : <StatusBadge tone="neutral">Locked</StatusBadge>}</td><td>{period.version}</td><td>{formatDateTime(period.locked_at)}</td><td>{period.status === "open" ? <button className="button button-ghost" type="button" aria-label={`Lock ${period.name}`} onClick={() => handleLockPeriod(period)} disabled={lockingPeriodId === period.id}><LockKeyhole size={14} aria-hidden="true" /> {lockingPeriodId === period.id ? "Locking…" : `Lock ${period.name}`}</button> : <span className="muted-cell">Closed</span>}</td></tr>) : <tr><td className="muted-cell" colSpan={6}>{viewState === "loading" ? "Loading periods…" : viewState === "error" ? "Periods unavailable" : viewState === "ready" ? "No periods match the current filters" : "No connected periods"}</td></tr>}</tbody></>}
          </table>
        </div>
        {viewState === "ready" && ((surface === "accounts" && visibleAccounts.length === 0) || (surface === "periods" && visiblePeriods.length === 0)) ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><Icon size={20} /></span><strong>{page.emptyTitle}</strong><p>{page.emptyDescription}</p><StatusBadge tone="warning"><CircleHelp size={12} aria-hidden="true" /> Actions remain guarded</StatusBadge></div> : null}
      </section>
    </div>
  );
}
