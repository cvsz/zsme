"use client";

import {
  ArrowDownLeft,
  ArrowDownToLine,
  ArrowUpRight,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  FileCheck2,
  FilePlus2,
  Filter,
  Link2,
  LockKeyhole,
  ReceiptText,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
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
import { formatMoney } from "@/lib/documents";
import { listDocuments, type DocumentKind, type FinancialDocument } from "@/lib/documents";
import { listPartners, type Partner } from "@/lib/partners";
import {
  createPayment,
  createPaymentIdempotencyKey,
  listPayments,
  postPayment,
  type PaymentKind,
  type PaymentRecord,
  type PaymentStatus,
} from "@/lib/payments";

const copy = {
  receipt: {
    eyebrow: "Accounts receivable",
    title: "Customer receipts",
    subtitle: "Record incoming cash, allocate it to one or more posted invoices and keep residual advances explicit.",
    action: "Record receipt",
    partner: "customer",
    partnerType: "customer" as const,
    documentKind: "invoice" as DocumentKind,
    plural: "receipts",
    control: "Cash in",
    icon: ArrowDownLeft,
  },
  disbursement: {
    eyebrow: "Accounts payable",
    title: "Vendor disbursements",
    subtitle: "Record outgoing cash, settle supplier bills and preserve payment evidence through an auditable ledger trail.",
    action: "Record disbursement",
    partner: "vendor",
    partnerType: "vendor" as const,
    documentKind: "bill" as DocumentKind,
    plural: "disbursements",
    control: "Cash out",
    icon: ArrowUpRight,
  },
} as const;

const controls = [
  { label: "Draft", description: "Capture amount and allocation", icon: ReceiptText },
  { label: "Review", description: "Confirm partner and residual", icon: ShieldCheck },
  { label: "Post", description: "Create balanced journal entry", icon: FileCheck2 },
  { label: "Reconcile", description: "Trace cash to statement", icon: CheckCircle2 },
] as const;

type LoadState = "idle" | "ready" | "error";
type FilterState = { status: PaymentStatus | "" };

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function readInitialFilters(): FilterState {
  if (typeof window === "undefined") {
    return { status: "" };
  }
  const status = new URLSearchParams(window.location.search).get("status");
  return { status: status === "draft" || status === "posted" || status === "void" ? status : "" };
}

function updateLocation(kind: PaymentKind, filters: FilterState): void {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  const query = params.toString();
  window.history.replaceState(null, "", `/${kind === "receipt" ? "receipts" : "disbursements"}${query ? `?${query}` : ""}`);
}

function safeError(error: unknown, action: "load" | "create" | "post", singular: string): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before using live payment data.";
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
        ? `This ${singular} cannot be posted until its allocation and ledger controls pass.`
        : `The ${singular} conflicts with current organization data.`;
    }
  }
  return action === "load"
    ? `Live ${singular} data is unavailable. Retry the request or review the API connection.`
    : `The ${singular} could not be ${action === "post" ? "posted" : "created"}. Review the fields and try again.`;
}

function filterState(current: FilterState, next: Partial<FilterState>, kind: PaymentKind): FilterState {
  const updated = { ...current, ...next };
  updateLocation(kind, updated);
  return updated;
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function statusTone(status: PaymentStatus): "neutral" | "success" | "warning" {
  if (status === "posted") {
    return "success";
  }
  if (status === "draft") {
    return "warning";
  }
  return "neutral";
}

export function PaymentWorkbench({ kind }: Readonly<{ kind: PaymentKind }>) {
  const page = copy[kind];
  const MovementIcon = page.icon;
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [filters, setFilters] = useState<FilterState>(readInitialFilters);
  const [payments, setPayments] = useState<PaymentRecord[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [documents, setDocuments] = useState<FinancialDocument[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [postingId, setPostingId] = useState<string | null>(null);
  const [selectedPartnerId, setSelectedPartnerId] = useState("");

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;
  const visiblePayments = viewState === "disconnected" || viewState === "unauthenticated" ? [] : payments;
  const partnerNames = new Map(partners.map((partner) => [partner.id, partner.display_name]));
  const selectedDocuments = documents.filter((document) => !selectedPartnerId || document.partner_id === selectedPartnerId);

  useEffect(() => {
    const controller = new AbortController();
    if (!configuredEndpoint || !getAccessToken()) {
      return () => controller.abort();
    }

    Promise.all([
      listPayments(kind, { status: filters.status || undefined }, controller.signal),
      listPartners({ partnerType: page.partnerType }, controller.signal),
      listDocuments(page.documentKind, { status: "posted" }, controller.signal),
    ])
      .then(([paymentResult, partnerResult, documentResult]) => {
        if (!controller.signal.aborted) {
          setPayments(paymentResult);
          setPartners(partnerResult);
          setDocuments(documentResult);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(safeError(error, "load", kind === "receipt" ? "receipt" : "disbursement"));
          setLoadState("error");
        }
      });

    return () => controller.abort();
  }, [configuredEndpoint, filters, kind, page.documentKind, page.partnerType, refreshNonce]);

  const handleTab = (event: MouseEvent<HTMLAnchorElement>, next: Partial<FilterState>) => {
    event.preventDefault();
    setPayments([]);
    setLoadState("idle");
    setFilters((current) => filterState(current, next, kind));
  };

  const handlePost = async (payment: PaymentRecord) => {
    const singular = kind === "receipt" ? "receipt" : "disbursement";
    setPostingId(payment.id);
    setActionError("");
    try {
      const posted = await postPayment(kind, payment.id, createPaymentIdempotencyKey("post"));
      setPayments((current) => current.map((item) => item.id === posted.id ? posted : item));
      setNotice(`${singular[0].toUpperCase()}${singular.slice(1)} posted`);
    } catch (error: unknown) {
      setActionError(safeError(error, "post", singular));
    } finally {
      setPostingId(null);
    }
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const singular = kind === "receipt" ? "receipt" : "disbursement";
    setActionError("");
    const data = new FormData(event.currentTarget);
    const allocationDocumentId = String(data.get("allocation_document_id") || "");
    const allocationAmount = String(data.get("allocation_amount") || "").trim();
    const optional = (name: string) => {
      const value = String(data.get(name) || "").trim();
      return value || undefined;
    };
    const payload = {
      payment_number: String(data.get("payment_number") || "").trim(),
      partner_id: String(data.get("partner_id") || ""),
      payment_date: String(data.get("payment_date") || ""),
      currency_code: String(data.get("currency_code") || "THB").trim().toUpperCase(),
      amount: String(data.get("amount") || "").trim(),
      cash_account_code: String(data.get("cash_account_code") || "").trim(),
      unapplied_account_code: optional("unapplied_account_code"),
      memo: optional("memo"),
      allocations: allocationDocumentId && allocationAmount
        ? [{ document_id: allocationDocumentId, amount: allocationAmount }]
        : [],
    };

    setIsCreating(true);
    try {
      const created = await createPayment(kind, payload, createPaymentIdempotencyKey("create"));
      setPayments((current) => [created, ...current]);
      setIsCreateOpen(false);
      setNotice(`Draft ${singular} created`);
    } catch (error: unknown) {
      setActionError(safeError(error, "create", singular));
    } finally {
      setIsCreating(false);
    }
  };

  const openCount = visiblePayments.filter((payment) => payment.status === "draft").length;
  const postedCount = visiblePayments.filter((payment) => payment.status === "posted").length;
  const totalAmount = visiblePayments.reduce((total, payment) => total + Number(payment.amount), 0);
  const unappliedAmount = visiblePayments.reduce((total, payment) => {
    const allocated = payment.allocations.reduce((sum, allocation) => sum + Number(allocation.amount), 0);
    return total + Math.max(Number(payment.amount) - allocated, 0);
  }, 0);
  const singular = kind === "receipt" ? "receipt" : "disbursement";
  const statusLabel = {
    idle: "Loading workspace",
    loading: "Loading live data",
    ready: `${visiblePayments.length} live ${page.plural}`,
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
          <button className="button button-primary" type="button" disabled={!canUseWorkspace || viewState !== "ready" || partners.length === 0} onClick={() => { setActionError(""); setSelectedPartnerId(""); setIsCreateOpen(true); }}>
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
                {viewState === "error" ? `${page.title} data needs attention` : "Cash movements stay guarded until the workspace connects"}
              </strong>
              <p>
                {viewState === "disconnected"
                  ? "Connect the API to load organization data. No financial values are fabricated in this interface."
                  : viewState === "unauthenticated"
                    ? "Sign in with an organization account before reading or changing cash movements."
                    : viewState === "error"
                      ? loadError
                      : "Allocations are checked against posted documents, open balances and the current organization's permissions."}
              </p>
            </div>
          </div>
          <div className="page-actions">
            {viewState === "error" ? (
              <button className="button button-secondary" type="button" onClick={() => { setPayments([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}>
                <RefreshCw size={15} aria-hidden="true" /> Retry {page.plural} load
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

      {isCreateOpen ? (
        <section className="panel" aria-labelledby={`${kind}-create-title`}>
          <div className="section-heading-row">
            <div className="section-heading">
              <h2 id={`${kind}-create-title`}>{page.action}</h2>
              <p>Capture the movement and its allocation; posting remains a separate explicit control action.</p>
            </div>
            <button className="icon-button" type="button" aria-label={`Close create ${singular} form`} onClick={() => setIsCreateOpen(false)}>
              <X size={17} aria-hidden="true" />
            </button>
          </div>
          <form className="form-grid" onSubmit={handleCreate}>
            <div className="panel-grid two-column">
              <div className="field">
                <label htmlFor={`${kind}-payment-number`}>Payment number</label>
                <input id={`${kind}-payment-number`} name="payment_number" required maxLength={100} placeholder={kind === "receipt" ? "REC-0001" : "PAY-0001"} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-payment-partner`}>Partner</label>
                <select id={`${kind}-payment-partner`} name="partner_id" required defaultValue="" onChange={(event) => setSelectedPartnerId(event.target.value)}>
                  <option value="">Select {page.partner}</option>
                  {partners.filter((partner) => partner.is_active).map((partner) => <option key={partner.id} value={partner.id}>{partner.partner_code} · {partner.display_name}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor={`${kind}-payment-date`}>Payment date</label>
                <input id={`${kind}-payment-date`} name="payment_date" type="date" required defaultValue={todayIso()} />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-currency`}>Currency</label>
                <input id={`${kind}-currency`} name="currency_code" required minLength={3} maxLength={3} defaultValue="THB" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-amount`}>Payment amount</label>
                <input id={`${kind}-amount`} name="amount" type="number" min="0.01" step="0.01" required placeholder="0.00" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-cash-account`}>Cash account</label>
                <input id={`${kind}-cash-account`} name="cash_account_code" required defaultValue="1001" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-allocation-document`}>Allocate to document</label>
                <select id={`${kind}-allocation-document`} name="allocation_document_id" defaultValue="">
                  <option value="">No allocation / advance</option>
                  {selectedDocuments.map((document) => <option key={document.id} value={document.id}>{document.document_number} · {formatMoney(document.total, document.currency_code)}</option>)}
                </select>
                <small>Only posted {page.partner} documents are eligible for allocation.</small>
              </div>
              <div className="field">
                <label htmlFor={`${kind}-allocation-amount`}>Allocation amount</label>
                <input id={`${kind}-allocation-amount`} name="allocation_amount" type="number" min="0.01" step="0.01" placeholder="Optional" />
              </div>
              <div className="field">
                <label htmlFor={`${kind}-unapplied-account`}>Unapplied account</label>
                <input id={`${kind}-unapplied-account`} name="unapplied_account_code" placeholder="Required for residual cash" />
                <small>Required when the payment amount exceeds its allocations.</small>
              </div>
            </div>
            <div className="field">
              <label htmlFor={`${kind}-memo`}>Memo</label>
              <textarea id={`${kind}-memo`} name="memo" maxLength={500} rows={3} placeholder="Optional settlement note" />
            </div>
            <div className="page-actions">
              <button className="button button-primary" type="submit" disabled={isCreating || partners.length === 0} aria-busy={isCreating}>
                <FilePlus2 size={15} aria-hidden="true" /> {isCreating ? "Creating…" : page.action}
              </button>
              <button className="button button-secondary" type="button" disabled={isCreating} onClick={() => setIsCreateOpen(false)}>Cancel</button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        <DataCard label={`Open ${page.plural}`} value={viewState === "ready" ? String(openCount) : "—"} meta="Draft movements in current view" icon={ReceiptText} />
        <DataCard label="Posted this view" value={viewState === "ready" ? String(postedCount) : "—"} meta="Immutable ledger-linked movements" icon={CheckCircle2} />
        <DataCard label="Gross amount" value={viewState === "ready" ? formatMoney(totalAmount.toFixed(2)) : "—"} meta="Loaded movement total · THB" icon={CircleDollarSign} />
        <DataCard label="Unapplied amount" value={viewState === "ready" ? formatMoney(unappliedAmount.toFixed(2)) : "—"} meta="Residual cash requiring review" icon={LockKeyhole} />
      </section>

      <nav className="tab-list" aria-label={`${page.title} sections`}>
        <a href={`/${page.plural}`} aria-current={!filters.status ? "page" : undefined} onClick={(event) => handleTab(event, { status: "" })}>All {page.plural}</a>
        <a href={`/${page.plural}?status=draft`} aria-current={filters.status === "draft" ? "page" : undefined} onClick={(event) => handleTab(event, { status: "draft" })}>Draft</a>
        <a href={`/${page.plural}?status=posted`} aria-current={filters.status === "posted" ? "page" : undefined} onClick={(event) => handleTab(event, { status: "posted" })}>Posted</a>
        <a href={`/${page.plural}?status=void`} aria-current={filters.status === "void" ? "page" : undefined} onClick={(event) => handleTab(event, { status: "void" })}>Voided</a>
      </nav>

      <section className="panel" aria-labelledby={`${kind}-register-title`}>
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id={`${kind}-register-title`}>{page.title} register</h2>
              <p>Each movement retains partner, allocation, cash-account and ledger references.</p>
            </div>
            <StatusBadge tone="info"><MovementIcon size={12} aria-hidden="true" /> {page.control}</StatusBadge>
          </div>
        </div>
        <div className="workbench-toolbar" aria-label={`${page.title} filters`}>
          <label className="search-trigger workbench-search" htmlFor={`${kind}-search`}>
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search {page.plural}</span>
            <input id={`${kind}-search`} type="search" placeholder={`Search by number or ${page.partner}`} disabled />
          </label>
          <label className="visually-hidden" htmlFor={`${kind}-status-filter`}>Payment status filter</label>
          <select id={`${kind}-status-filter`} className="filter-select" aria-label="Payment status filter" value={filters.status} onChange={(event) => {
            const value = event.target.value;
            setPayments([]);
            setLoadState("idle");
            setFilters((current) => filterState(current, { status: value === "draft" || value === "posted" || value === "void" ? value : "" }, kind));
          }} disabled={!canUseWorkspace || viewState === "loading"}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="posted">Posted</option>
            <option value="void">Voided</option>
          </select>
          <span className="page-subtitle"><CalendarClock size={14} aria-hidden="true" /> Fiscal year 2026 · THB</span>
        </div>
        <div className="data-table-wrap" tabIndex={0} aria-label={`Scroll ${page.plural} register horizontally`} aria-busy={viewState === "loading"}>
          <table className="data-table">
            <caption>{page.title} register</caption>
            <thead>
              <tr>
                <th scope="col">Payment</th>
                <th scope="col">{page.partner}</th>
                <th scope="col">Date</th>
                <th scope="col">Amount</th>
                <th scope="col">Allocation</th>
                <th scope="col">Status</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {visiblePayments.length > 0 ? visiblePayments.map((payment) => {
                const allocated = payment.allocations.reduce((sum, allocation) => sum + Number(allocation.amount), 0);
                return (
                  <tr key={payment.id}>
                    <td><strong>{payment.payment_number}</strong><small className="table-secondary">{payment.allocations.length} allocation{payment.allocations.length === 1 ? "" : "s"}</small></td>
                    <td>{partnerNames.get(payment.partner_id) || "Partner identity unavailable"}</td>
                    <td>{formatDate(payment.payment_date)}</td>
                    <td><strong>{formatMoney(payment.amount, payment.currency_code)}</strong></td>
                    <td>{formatMoney(allocated.toFixed(2), payment.currency_code)}</td>
                    <td><StatusBadge tone={statusTone(payment.status)}>{payment.status[0].toUpperCase() + payment.status.slice(1)}</StatusBadge></td>
                    <td>{payment.status === "draft" ? <button className="button button-secondary" type="button" onClick={() => handlePost(payment)} disabled={postingId !== null} aria-busy={postingId === payment.id} aria-label={`Post ${singular} ${payment.payment_number}`}><Send size={14} aria-hidden="true" /> {postingId === payment.id ? "Posting…" : `Post ${singular}`}</button> : <StatusBadge tone="success"><FileCheck2 size={12} aria-hidden="true" /> Ledger linked</StatusBadge>}</td>
                  </tr>
                );
              }) : (
                <tr><td className="muted-cell" colSpan={7}>{viewState === "loading" ? `Loading ${page.plural}…` : viewState === "error" ? `${page.title} unavailable` : viewState === "ready" ? `No ${page.plural} to display` : `No connected ${page.plural}`}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {viewState === "ready" && visiblePayments.length === 0 ? (
          <div className="empty-state workbench-empty">
            <span className="empty-state-icon" aria-hidden="true"><MovementIcon size={20} /></span>
            <strong>No {page.plural} to display</strong>
            <p>Record a controlled {singular} for an active {page.partner}, then review and post it to the ledger.</p>
            <StatusBadge tone="info"><ArrowDownToLine size={12} aria-hidden="true" /> Ready for controlled entry</StatusBadge>
          </div>
        ) : null}
      </section>

      <section className="panel" aria-labelledby={`${kind}-controls-title`}>
        <div className="section-heading">
          <h2 id={`${kind}-controls-title`}>Settlement controls</h2>
          <p>Balances remain reproducible from immutable documents, payment allocations and posted ledger lines.</p>
        </div>
        <ol className="workflow-rail">
          {controls.map(({ label, description, icon: ControlIcon }, index) => (
            <li key={label} className={index === 0 ? "is-current" : undefined}>
              <span className="workflow-icon" aria-hidden="true"><ControlIcon size={17} /></span>
              <span><strong>{label}</strong><small>{description}</small></span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
