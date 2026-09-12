"use client";

import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  FileCheck2,
  FilePlus2,
  FileText,
  Filter,
  Link2,
  LockKeyhole,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, type MouseEvent, useEffect, useState, useSyncExternalStore } from "react";

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
  createDocument,
  createDocumentIdempotencyKey,
  formatMoney,
  listDocuments,
  postDocument,
  type DocumentKind,
  type DocumentStatus,
  type FinancialDocument,
} from "@/lib/documents";
import { listPartners, type Partner } from "@/lib/partners";

const copy = {
  invoice: {
    eyebrow: "Accounts receivable",
    title: "Sales invoices",
    subtitle: "Issue customer invoices, post revenue and keep every receivable traceable to an auditable ledger entry.",
    singular: "invoice",
    plural: "invoices",
    partner: "customer",
    partnerType: "customer" as const,
    control: "Accounts receivable",
    action: "Create invoice",
    empty: "No invoices to display",
    emptyDescription: "Create a draft invoice for an active customer, then post it after review.",
    directionIcon: ArrowUpFromLine,
    accentIcon: CircleDollarSign,
    controlAccount: "1100",
    lineAccount: "4000",
    taxAccount: "2101",
  },
  bill: {
    eyebrow: "Accounts payable",
    title: "Vendor bills",
    subtitle: "Capture supplier bills, route them through review and post payable obligations with tax-aware double-entry controls.",
    singular: "bill",
    plural: "bills",
    partner: "vendor",
    partnerType: "vendor" as const,
    control: "Accounts payable",
    action: "Create bill",
    empty: "No bills to display",
    emptyDescription: "Create a draft bill for an active vendor, then post it after review.",
    directionIcon: ArrowDownToLine,
    accentIcon: FileText,
    controlAccount: "2100",
    lineAccount: "5000",
    taxAccount: "1400",
  },
} as const;

const workflow = [
  { label: "Draft", detail: "Prepare line items and tax details", icon: FileText },
  { label: "Review", detail: "Validate partner, accounts and approvals", icon: ShieldCheck },
  { label: "Post to ledger", detail: "Create one balanced immutable entry", icon: Send },
  { label: "Reconcile", detail: "Track settlement against the document", icon: CheckCircle2 },
] as const;

type LoadState = "idle" | "ready" | "error";
type FilterState = { status: DocumentStatus | ""; search: string };

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function readInitialFilters(): FilterState {
  if (typeof window === "undefined") {
    return { status: "", search: "" };
  }
  const params = new URLSearchParams(window.location.search);
  const status = params.get("status");
  return {
    status: status === "draft" || status === "posted" || status === "void" ? status : "",
    search: params.get("search") || "",
  };
}

function updateLocation(kind: DocumentKind, filters: FilterState): void {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.search) {
    params.set("search", filters.search);
  }
  const query = params.toString();
  window.history.replaceState(null, "", `/${kind === "invoice" ? "invoices" : "bills"}${query ? `?${query}` : ""}`);
}

function clearCreateIntent(kind: DocumentKind): void {
  const params = new URLSearchParams(window.location.search);
  params.delete("create");
  const query = params.toString();
  window.history.replaceState(null, "", `/${kind === "invoice" ? "invoices" : "bills"}${query ? `?${query}` : ""}`);
}

function safeError(error: unknown, action: "load" | "create" | "post", singular: string): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before using live document data.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (error.status === 403) {
      return `Your role cannot ${action} ${singular}s in this organization.`;
    }
    if (error.status === 409) {
      return action === "post"
        ? `This ${singular} cannot be posted until its controls pass. Review the server response and try again.`
        : `The ${singular} conflicts with current organization data.`;
    }
  }
  return action === "load"
    ? `Live ${singular} data is unavailable. Retry the request or review the API connection.`
    : `The ${singular} could not be ${action === "post" ? "posted" : "created"}. Review the fields and try again.`;
}

function statusTone(status: DocumentStatus): "neutral" | "success" | "warning" {
  if (status === "posted") {
    return "success";
  }
  if (status === "draft") {
    return "warning";
  }
  return "neutral";
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function filterState(current: FilterState, next: Partial<FilterState>, kind: DocumentKind): FilterState {
  const updated = { ...current, ...next };
  updateLocation(kind, updated);
  return updated;
}

export function DocumentWorkbench({ kind }: Readonly<{ kind: DocumentKind }>) {
  const page = copy[kind];
  const DirectionIcon = page.directionIcon;
  const AccentIcon = page.accentIcon;
  const searchParams = useSearchParams();
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [filters, setFilters] = useState<FilterState>(readInitialFilters);
  const [draftSearch, setDraftSearch] = useState(filters.search);
  const [documents, setDocuments] = useState<FinancialDocument[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createIntentDismissed, setCreateIntentDismissed] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [postingId, setPostingId] = useState<string | null>(null);

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;
  const visibleDocuments = viewState === "disconnected" || viewState === "unauthenticated" ? [] : documents;
  const partnerNames = new Map(partners.map((partner) => [partner.id, partner.display_name]));
  const showCreateForm = isCreateOpen || (searchParams.get("create") === "1" && !createIntentDismissed);

  const closeCreate = () => {
    setIsCreateOpen(false);
    setCreateIntentDismissed(true);
    clearCreateIntent(kind);
  };

  useEffect(() => {
    const controller = new AbortController();
    if (!configuredEndpoint || !getAccessToken()) {
      return () => controller.abort();
    }

    Promise.all([
      listDocuments(kind, { status: filters.status || undefined, search: filters.search }, controller.signal),
      listPartners({ partnerType: page.partnerType }, controller.signal),
    ])
      .then(([result, partnerResult]) => {
        if (!controller.signal.aborted) {
          setDocuments(result);
          setPartners(partnerResult);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(safeError(error, "load", page.singular));
          setLoadState("error");
        }
      });

    return () => controller.abort();
  }, [configuredEndpoint, filters, kind, page.partnerType, page.singular, refreshNonce]);

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDocuments([]);
    setLoadState("idle");
    setFilters((current) => filterState(current, { search: draftSearch.trim() }, kind));
  };

  const handleTab = (event: MouseEvent<HTMLAnchorElement>, next: Partial<FilterState>) => {
    event.preventDefault();
    setDocuments([]);
    setLoadState("idle");
    setFilters((current) => filterState(current, next, kind));
  };

  const handlePost = async (document: FinancialDocument) => {
    setPostingId(document.id);
    setActionError("");
    try {
      const posted = await postDocument(kind, document.id, createDocumentIdempotencyKey("post"));
      setDocuments((current) => current.map((item) => item.id === posted.id ? posted : item));
      setNotice(`${page.singular[0].toUpperCase()}${page.singular.slice(1)} posted`);
    } catch (error: unknown) {
      setActionError(safeError(error, "post", page.singular));
    } finally {
      setPostingId(null);
    }
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    const optional = (name: string) => {
      const value = String(data.get(name) || "").trim();
      return value || undefined;
    };
    const payload = {
      document_number: String(data.get("document_number") || "").trim(),
      partner_id: String(data.get("partner_id") || ""),
      issue_date: String(data.get("issue_date") || ""),
      due_date: String(data.get("due_date") || ""),
      currency_code: String(data.get("currency_code") || "THB").trim().toUpperCase(),
      control_account_code: String(data.get("control_account_code") || "").trim(),
      tax_account_code: optional("tax_account_code"),
      memo: optional("memo"),
      lines: [{
        description: String(data.get("line_description") || "").trim(),
        quantity: String(data.get("quantity") || "1"),
        unit_price: String(data.get("unit_price") || "0"),
        tax_rate: String(data.get("tax_rate") || "0"),
        account_code: String(data.get("line_account_code") || "").trim(),
      }],
    };

    setIsCreating(true);
    try {
      const created = await createDocument(kind, payload, createDocumentIdempotencyKey("create"));
      setDocuments((current) => [created, ...current]);
      closeCreate();
      setNotice(`Draft ${page.singular} created`);
    } catch (error: unknown) {
      setActionError(safeError(error, "create", page.singular));
    } finally {
      setIsCreating(false);
    }
  };

  const openCount = visibleDocuments.filter((document) => document.status === "draft").length;
  const postedCount = visibleDocuments.filter((document) => document.status === "posted").length;
  const grossTotal = visibleDocuments.reduce((total, document) => total + Number(document.total), 0);
  const statusLabel = {
    idle: "Loading workspace",
    loading: "Loading live data",
    ready: `${visibleDocuments.length} live ${page.plural}`,
    disconnected: "API not connected",
    unauthenticated: "Sign-in required",
    error: "Data unavailable",
  }[viewState];
  const statusBadgeTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">{page.eyebrow}</p>
          <h1 className="page-title">{page.title}</h1>
          <p className="page-subtitle">{page.subtitle}</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone={statusBadgeTone}>{statusLabel}</StatusBadge>
          <button className="button button-primary" type="button" disabled={!canUseWorkspace || viewState !== "ready" || partners.length === 0} onClick={() => { setActionError(""); setCreateIntentDismissed(false); setIsCreateOpen(true); }}>
            <FilePlus2 size={15} aria-hidden="true" /> {page.action}
          </button>
        </div>
      </header>

      {viewState !== "ready" ? (
        <section className="connection-banner" aria-labelledby={`${kind}-connection-title`} role={viewState === "error" ? "alert" : undefined}>
          <div className="connection-banner-copy">
            <Link2 size={19} aria-hidden="true" />
            <div>
              <strong id={`${kind}-connection-title`}>
                {viewState === "error" ? `${page.title} data needs attention` : `Live ${page.plural} are guarded until the workspace connects`}
              </strong>
              <p>
                {viewState === "disconnected"
                  ? "Connect the API to load organization data. No financial values are fabricated in this interface."
                  : viewState === "unauthenticated"
                    ? "Sign in with an organization account before reading or changing financial documents."
                    : viewState === "error"
                      ? loadError
                      : "Data access, document creation and ledger posting use the signed-in tenant's organization boundary."}
              </p>
            </div>
          </div>
          <div className="page-actions">
            {viewState === "error" ? (
              <button className="button button-secondary" type="button" onClick={() => { setDocuments([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}>
                <RefreshCw size={15} aria-hidden="true" /> Retry {page.singular} load
              </button>
            ) : null}
            {viewState === "disconnected" || viewState === "unauthenticated" ? (
              <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>
                {viewState === "disconnected" ? "Review connection" : "Go to sign in"}
              </Link>
            ) : null}
          </div>
        </section>
      ) : null}

      {notice ? <p className="form-message" role="status" aria-live="polite">{notice}</p> : null}
      {actionError ? <p className="form-message" role="alert">{actionError}</p> : null}

      {showCreateForm ? (
        <section className="panel" aria-labelledby={`${kind}-create-title`}>
          <div className="section-heading-row">
            <div className="section-heading">
              <h2 id={`${kind}-create-title`}>{page.action}</h2>
              <p>Create a draft; posting remains a separate explicit control action.</p>
            </div>
            <button className="icon-button" type="button" aria-label={`Close create ${page.singular} form`} onClick={closeCreate}>
              <X size={17} aria-hidden="true" />
            </button>
          </div>
          <form className="form-grid" onSubmit={handleCreate}>
            <div className="panel-grid two-column">
              <div className="field">
                <label htmlFor={`${kind}-document-number`}>Document number</label>
                <input id={`${kind}-document-number`} name="document_number" required maxLength={100} placeholder={kind === "invoice" ? "INV-0001" : "BILL-0001"} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-partner`}>Partner</label>
                <select id={`${kind}-partner`} name="partner_id" required defaultValue="">
                  <option value="">Select {page.partner}</option>
                  {partners.filter((partner) => partner.is_active).map((partner) => <option key={partner.id} value={partner.id}>{partner.partner_code} · {partner.display_name}</option>)}
                </select>
                <small>Only active {page.partner}s from the authorized organization are available.</small>
              </div>
              <div className="field">
                <label htmlFor={`${kind}-issue-date`}>Issue date</label>
                <input id={`${kind}-issue-date`} name="issue_date" type="date" required defaultValue={todayIso()} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-due-date`}>Due date</label>
                <input id={`${kind}-due-date`} name="due_date" type="date" required defaultValue={todayIso()} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-currency`}>Currency</label>
                <input id={`${kind}-currency`} name="currency_code" required minLength={3} maxLength={3} defaultValue="THB" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-control-account`}>Control account</label>
                <input id={`${kind}-control-account`} name="control_account_code" required defaultValue={page.controlAccount} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-line-description`}>Line description</label>
                <input id={`${kind}-line-description`} name="line_description" required maxLength={500} placeholder="Service or item description" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-line-account`}>{kind === "invoice" ? "Revenue account" : "Expense account"}</label>
                <input id={`${kind}-line-account`} name="line_account_code" required defaultValue={page.lineAccount} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-quantity`}>Quantity</label>
                <input id={`${kind}-quantity`} name="quantity" type="number" min="0.001" step="0.001" required defaultValue="1" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-unit-price`}>Unit price</label>
                <input id={`${kind}-unit-price`} name="unit_price" type="number" min="0.01" step="0.01" required defaultValue="0" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-tax-rate`}>Tax rate (%)</label>
                <input id={`${kind}-tax-rate`} name="tax_rate" type="number" min="0" max="100" step="0.01" required defaultValue="7" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-tax-account`}>Tax account</label>
                <input id={`${kind}-tax-account`} name="tax_account_code" required defaultValue={page.taxAccount} />
              </div>
            </div>
            <div className="field">
              <label htmlFor={`${kind}-memo`}>Memo</label>
              <textarea id={`${kind}-memo`} name="memo" maxLength={500} rows={3} placeholder="Optional internal note" />
            </div>
            <div className="page-actions">
              <button className="button button-primary" type="submit" disabled={isCreating || partners.length === 0} aria-busy={isCreating}>
                <FilePlus2 size={15} aria-hidden="true" /> {isCreating ? "Creating…" : page.action}
              </button>
              <button className="button button-secondary" type="button" disabled={isCreating} onClick={closeCreate}>Cancel</button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        <DataCard label={`Open ${page.plural}`} value={viewState === "ready" ? String(openCount) : "—"} meta="Draft documents in current view" icon={page.directionIcon} />
        <DataCard label="Posted this view" value={viewState === "ready" ? String(postedCount) : "—"} meta="Immutable ledger-linked documents" icon={CheckCircle2} />
        <DataCard label="Gross total" value={viewState === "ready" ? formatMoney(grossTotal.toFixed(2)) : "—"} meta="Loaded document total · THB" icon={AccentIcon} />
        <DataCard label="Control health" value={viewState === "ready" ? "Review" : "—"} meta="Posting remains permission-gated" status={viewState === "ready" ? "Policy path" : "Not evaluated"} icon={LockKeyhole} />
      </section>

      <nav className="tab-list" aria-label={`${page.title} sections`}>
        <a href={`/${page.plural}`} aria-current={!filters.status ? "page" : undefined} onClick={(event) => handleTab(event, { status: "" })}>All {page.plural}</a>
        <a href={`/${page.plural}?status=draft`} aria-current={filters.status === "draft" ? "page" : undefined} onClick={(event) => handleTab(event, { status: "draft" })}>Draft</a>
        <a href={`/${page.plural}?status=posted`} aria-current={filters.status === "posted" ? "page" : undefined} onClick={(event) => handleTab(event, { status: "posted" })}>Posted</a>
        <a href={`/${page.plural}?status=void`} aria-current={filters.status === "void" ? "page" : undefined} onClick={(event) => handleTab(event, { status: "void" })}>Voided</a>
      </nav>

      <section className="panel" aria-labelledby={`${kind}-directory-title`}>
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id={`${kind}-directory-title`}>{page.title} register</h2>
              <p>Every document carries a unique number, fixed-precision totals and a verifiable posting lineage.</p>
            </div>
            <StatusBadge tone="info"><DirectionIcon size={12} aria-hidden="true" /> {page.control}</StatusBadge>
          </div>
        </div>
        <form className="workbench-toolbar" aria-label={`${page.title} filters`} onSubmit={handleSearch}>
          <label className="search-trigger workbench-search" htmlFor={`${kind}-search`}>
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search {page.plural}</span>
            <input id={`${kind}-search`} type="search" value={draftSearch} onChange={(event) => setDraftSearch(event.target.value)} placeholder={`Search by number or ${page.partner}`} disabled={!canUseWorkspace || viewState === "loading"} />
          </label>
          <label className="visually-hidden" htmlFor={`${kind}-status-filter`}>Document status filter</label>
          <select id={`${kind}-status-filter`} className="filter-select" aria-label="Document status filter" value={filters.status} onChange={(event) => {
            const value = event.target.value;
            setDocuments([]);
            setLoadState("idle");
            setFilters((current) => filterState(current, { status: value === "draft" || value === "posted" || value === "void" ? value : "" }, kind));
          }} disabled={!canUseWorkspace || viewState === "loading"}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="posted">Posted</option>
            <option value="void">Voided</option>
          </select>
          <button className="button button-secondary" type="submit" disabled={!canUseWorkspace || viewState === "loading"}>
            <Filter size={15} aria-hidden="true" /> Apply filters
          </button>
          <span className="page-subtitle"><CalendarClock size={14} aria-hidden="true" /> Organization ledger scope</span>
        </form>
        <div className="data-table-wrap" tabIndex={0} aria-label={`Scroll ${page.plural} register horizontally`} aria-busy={viewState === "loading"}>
          <table className="data-table">
            <caption>{page.title} register</caption>
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">{page.partner}</th>
                <th scope="col">Issue date</th>
                <th scope="col">Due date</th>
                <th scope="col">Total</th>
                <th scope="col">Status</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {visibleDocuments.length > 0 ? visibleDocuments.map((document) => (
                <tr key={document.id}>
                  <td><strong>{document.document_number}</strong><small className="table-secondary">{document.lines.length} line{document.lines.length === 1 ? "" : "s"}</small></td>
                  <td>{partnerNames.get(document.partner_id) || "Partner identity unavailable"}</td>
                  <td>{formatDate(document.issue_date)}</td>
                  <td>{formatDate(document.due_date)}</td>
                  <td><strong>{formatMoney(document.total, document.currency_code)}</strong></td>
                  <td><StatusBadge tone={statusTone(document.status)}>{document.status[0].toUpperCase() + document.status.slice(1)}</StatusBadge></td>
                  <td>{document.status === "draft" ? <button className="button button-secondary" type="button" onClick={() => handlePost(document)} disabled={postingId !== null} aria-busy={postingId === document.id} aria-label={`Post ${page.singular} ${document.document_number}`}><Send size={14} aria-hidden="true" /> {postingId === document.id ? "Posting…" : `Post ${page.singular}`}</button> : <StatusBadge tone="success"><FileCheck2 size={12} aria-hidden="true" /> Ledger linked</StatusBadge>}</td>
                </tr>
              )) : (
                <tr><td className="muted-cell" colSpan={7}>{viewState === "loading" ? `Loading ${page.plural}…` : viewState === "error" ? `${page.title} unavailable` : viewState === "ready" ? page.empty : `No connected ${page.plural}`}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {viewState === "ready" && visibleDocuments.length === 0 ? (
          <div className="empty-state workbench-empty">
            <span className="empty-state-icon" aria-hidden="true"><FileText size={20} /></span>
            <strong>{page.empty}</strong>
            <p>{page.emptyDescription}</p>
            <StatusBadge tone="info"><LockKeyhole size={12} aria-hidden="true" /> Ready for controlled entry</StatusBadge>
          </div>
        ) : null}
      </section>

      <section className="panel" aria-labelledby={`${kind}-workflow-title`}>
        <div className="section-heading">
          <h2 id={`${kind}-workflow-title`}>Controlled document lifecycle</h2>
          <p>Workflow visibility stays available even when live tenant data is unavailable.</p>
        </div>
        <ol className="workflow-rail">
          {workflow.map(({ label, detail, icon: Icon }, index) => (
            <li key={label} className={index === 0 ? "is-current" : undefined}>
              <span className="workflow-icon" aria-hidden="true"><Icon size={17} /></span>
              <span><strong>{label}</strong><small>{detail}</small></span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

export function DocumentWorkbenchFallback({ kind }: Readonly<{ kind: DocumentKind }>) {
  const page = copy[kind];

  return (
    <div className="page-stack" aria-busy="true">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">{page.eyebrow}</p>
          <h1 className="page-title">{page.title}</h1>
          <p className="page-subtitle">Loading the governed {page.singular} workspace…</p>
        </div>
      </header>
      <section className="panel loading-panel" aria-label={`Loading ${page.plural}`}>
        <RefreshCw className="spin" size={18} aria-hidden="true" />
        <span>Preparing live document controls</span>
      </section>
    </div>
  );
}
