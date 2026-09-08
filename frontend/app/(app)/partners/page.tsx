"use client";

import {
  Archive,
  Building2,
  ContactRound,
  FilePlus2,
  Filter,
  Link2,
  Pencil,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Tags,
  X,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState, useSyncExternalStore } from "react";

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
  archivePartner,
  createPartner,
  createPartnerIdempotencyKey,
  listPartners,
  updatePartner,
  type CreatePartnerInput,
  type Partner,
  type PartnerType,
  type UpdatePartnerInput,
} from "@/lib/partners";

type LoadState = "idle" | "ready" | "error";
type FilterState = {
  partnerType: PartnerType | "";
  search: string;
  includeArchived: boolean;
};

const defaultFilters: FilterState = {
  partnerType: "",
  search: "",
  includeArchived: false,
};

function isPartnerType(value: string | null): value is PartnerType {
  return value === "customer" || value === "vendor" || value === "both";
}

function readInitialFilters(): FilterState {
  if (typeof window === "undefined") {
    return defaultFilters;
  }
  const params = new URLSearchParams(window.location.search);
  const type = params.get("type");
  return {
    partnerType: isPartnerType(type) ? type : "",
    search: params.get("search") || "",
    includeArchived: params.get("archived") === "true",
  };
}

function updateLocation(filters: FilterState): void {
  const params = new URLSearchParams();
  if (filters.partnerType) {
    params.set("type", filters.partnerType);
  }
  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.includeArchived) {
    params.set("archived", "true");
  }
  const query = params.toString();
  window.history.replaceState(null, "", `/partners${query ? `?${query}` : ""}`);
}

function errorMessage(error: unknown, action: "load" | "create" | "update" | "archive"): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before using partner data.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (error.status === 403) {
      if (action === "create") return "Your role cannot create partners in this organization.";
      if (action === "update") return "Your role cannot update partners in this organization.";
      if (action === "archive") return "Your role cannot archive partners in this organization.";
      return "Your role cannot view partners in this organization.";
    }
    if (error.status === 409) {
      if (action === "create") return "That partner code already exists or the request conflicts with current data.";
      if (action === "update") return "The partner changed elsewhere. Reload it before saving again.";
      if (action === "archive") return "The partner changed elsewhere or is already archived. Reload the directory.";
    }
  }
  if (action === "load") return "Partner data is unavailable. Retry the request or review the API connection.";
  if (action === "update") return "Partner could not be updated. Review the fields and try again.";
  if (action === "archive") return "Partner could not be archived. Review the current record and try again.";
  return "Partner could not be created. Review the fields and try again.";
}

function formatPartnerType(type: PartnerType): string {
  if (type === "both") {
    return "Customer & vendor";
  }
  return type[0].toUpperCase() + type.slice(1);
}

function updateFilters(current: FilterState, next: Partial<FilterState>): FilterState {
  const updated = { ...current, ...next };
  updateLocation(updated);
  return updated;
}

export default function PartnersPage() {
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [filters, setFilters] = useState<FilterState>(readInitialFilters);
  const [draftSearch, setDraftSearch] = useState(filters.search);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingPartner, setEditingPartner] = useState<Partner | null>(null);
  const [archiveCandidate, setArchiveCandidate] = useState<Partner | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [actionError, setActionError] = useState("");

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;
  const visiblePartners = viewState === "disconnected" || viewState === "unauthenticated" ? [] : partners;

  useEffect(() => {
    const controller = new AbortController();

    if (!configuredEndpoint || !getAccessToken()) {
      return () => controller.abort();
    }

    listPartners(
      {
        partnerType: filters.partnerType || undefined,
        search: filters.search,
        includeArchived: filters.includeArchived,
      },
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setPartners(result);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(errorMessage(error, "load"));
          setLoadState("error");
        }
      });

    return () => controller.abort();
  }, [configuredEndpoint, filters, refreshNonce]);

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPartners([]);
    setLoadState("idle");
    setFilters((current) => updateFilters(current, { search: draftSearch.trim() }));
  };

  const handleTab = (
    event: React.MouseEvent<HTMLAnchorElement>,
    next: Partial<FilterState>,
  ) => {
    event.preventDefault();
    setPartners([]);
    setLoadState("idle");
    setFilters((current) => updateFilters(current, next));
  };

  const openCreate = () => {
    setActionError("");
    setEditingPartner(null);
    setIsCreateOpen(true);
  };

  const openEdit = (partner: Partner) => {
    setActionError("");
    setIsCreateOpen(false);
    setEditingPartner(partner);
  };

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    const optionalValue = (name: string) => {
      const value = String(data.get(name) || "").trim();
      return value || undefined;
    };
    setIsSaving(true);
    try {
      if (editingPartner) {
        const payload: UpdatePartnerInput = {
          expected_version: editingPartner.version,
          display_name: String(data.get("display_name") || "").trim(),
          legal_name: optionalValue("legal_name") || null,
          tax_id: optionalValue("tax_id") || null,
          tax_branch: optionalValue("tax_branch") || null,
          email: optionalValue("email") || null,
          phone: optionalValue("phone") || null,
          payment_terms_days: Number(data.get("payment_terms_days") || 0),
          credit_limit: String(data.get("credit_limit") || "0.00").trim(),
        };
        const updated = await updatePartner(editingPartner.id, payload, createPartnerIdempotencyKey("update"));
        setPartners((current) => current.map((partner) => partner.id === updated.id ? updated : partner));
        setNotice("Partner updated");
      } else {
        const payload: CreatePartnerInput = {
          partner_code: String(data.get("partner_code") || "").trim(),
          partner_type: String(data.get("partner_type") || "customer") as PartnerType,
          display_name: String(data.get("display_name") || "").trim(),
          legal_name: optionalValue("legal_name"),
          tax_id: optionalValue("tax_id"),
          tax_branch: optionalValue("tax_branch"),
          email: optionalValue("email"),
          phone: optionalValue("phone"),
          payment_terms_days: Number(data.get("payment_terms_days") || 0),
          credit_limit: String(data.get("credit_limit") || "0.00").trim(),
        };
        const created = await createPartner(payload, createPartnerIdempotencyKey());
        setPartners((current) => [...current, created].sort((left, right) => left.partner_code.localeCompare(right.partner_code)));
        setNotice("Partner created");
      }
      setEditingPartner(null);
      setIsCreateOpen(false);
    } catch (error: unknown) {
      setActionError(errorMessage(error, editingPartner ? "update" : "create"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleArchive = async () => {
    if (!archiveCandidate) return;
    setActionError("");
    setIsSaving(true);
    try {
      const archived = await archivePartner(
        archiveCandidate.id,
        archiveCandidate.version,
        createPartnerIdempotencyKey("archive"),
      );
      setPartners((current) => filters.includeArchived
        ? current.map((partner) => partner.id === archived.id ? archived : partner)
        : current.filter((partner) => partner.id !== archived.id));
      setArchiveCandidate(null);
      setNotice("Partner archived");
    } catch (error: unknown) {
      setActionError(errorMessage(error, "archive"));
    } finally {
      setIsSaving(false);
    }
  };

  const statusLabel = {
    idle: "Loading workspace",
    loading: "Loading live data",
    ready: `${partners.length} live ${partners.length === 1 ? "partner" : "partners"}`,
    disconnected: "API not connected",
    unauthenticated: "Sign-in required",
    error: "Data unavailable",
  }[viewState];
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";
  const formIsOpen = isCreateOpen || Boolean(editingPartner);
  const formIsEdit = Boolean(editingPartner);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Partner master</p>
          <h1 className="page-title">Customers & vendors</h1>
          <p className="page-subtitle">Keep customer, supplier and business-partner identity consistent across sales, purchasing and the ledger.</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone={statusTone}>{statusLabel}</StatusBadge>
          <button className="button button-primary" type="button" disabled={!canUseWorkspace} onClick={openCreate}>
            <FilePlus2 size={15} aria-hidden="true" /> Add partner
          </button>
        </div>
      </header>

      {viewState !== "ready" ? (
        <section className="connection-banner" aria-labelledby="partner-connection-title" role={viewState === "error" ? "alert" : undefined}>
          <div className="connection-banner-copy">
            <Link2 size={19} aria-hidden="true" />
            <div>
              <strong id="partner-connection-title">
                {viewState === "error" ? "Partner data needs attention" : "Partner records stay tenant-scoped"}
              </strong>
              <p>
                {viewState === "disconnected"
                  ? "Connect the API to load organization data. No customer or vendor data is fabricated in this interface."
                  : viewState === "unauthenticated"
                    ? "Sign in with an organization account before reading or changing partner records."
                    : viewState === "error"
                      ? loadError
                      : "Partner data access is protected by server-side authorization and organization boundaries."}
              </p>
            </div>
          </div>
          <div className="page-actions">
            {viewState === "error" ? (
              <button className="button button-secondary" type="button" onClick={() => { setPartners([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}>
                <RefreshCw size={15} aria-hidden="true" /> Retry partner load
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

      {archiveCandidate ? (
        <section className="connection-banner" aria-labelledby="archive-partner-title" role="alert">
          <div className="connection-banner-copy">
            <Archive size={19} aria-hidden="true" />
            <div>
              <strong id="archive-partner-title">Archive {archiveCandidate.partner_code}?</strong>
              <p>{archiveCandidate.display_name} will leave active partner lists. Existing posted documents and audit history remain unchanged.</p>
            </div>
          </div>
          <div className="page-actions">
            <button className="button button-danger" type="button" onClick={handleArchive} disabled={isSaving} aria-busy={isSaving}><Archive size={15} aria-hidden="true" /> {isSaving ? "Archiving…" : "Confirm archive"}</button>
            <button className="button button-secondary" type="button" onClick={() => setArchiveCandidate(null)} disabled={isSaving}>Cancel</button>
          </div>
        </section>
      ) : null}

      {formIsOpen ? (
        <section className="panel" aria-labelledby="create-partner-title">
          <div className="section-heading-row">
            <div className="section-heading">
              <h2 id="create-partner-title">{formIsEdit ? "Edit partner" : "Create partner"}</h2>
              <p>{formIsEdit ? "Changes use the current record version and append an audit event." : "Start with the required identity fields. Server policy validates the organization boundary and duplicate code."}</p>
            </div>
            <button className="icon-button" type="button" aria-label="Close partner form" onClick={() => { setIsCreateOpen(false); setEditingPartner(null); }}>
              <X size={17} aria-hidden="true" />
            </button>
          </div>
          <form className="form-grid" onSubmit={handleSave}>
            <div className="panel-grid two-column">
              <div className="field">
                <label htmlFor="partner-code">Partner code</label>
                <input id="partner-code" name="partner_code" required minLength={2} maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9._/-]*" placeholder="CUS-0001" defaultValue={editingPartner?.partner_code || ""} readOnly={formIsEdit} />
                <small>Stable code used across documents and reports.</small>
              </div>
              <div className="field">
                <label htmlFor="partner-type">Partner type</label>
                <select id="partner-type" name="partner_type" defaultValue={editingPartner?.partner_type || "customer"} disabled={formIsEdit}>
                  <option value="customer">Customer</option>
                  <option value="vendor">Vendor</option>
                  <option value="both">Customer & vendor</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="partner-name">Partner name</label>
                <input id="partner-name" name="display_name" required maxLength={250} placeholder="Company or person name" defaultValue={editingPartner?.display_name || ""} />
              </div>
              <div className="field">
                <label htmlFor="legal-name">Legal name</label>
                <input id="legal-name" name="legal_name" maxLength={250} placeholder="Registered legal name" defaultValue={editingPartner?.legal_name || ""} />
              </div>
              <div className="field">
                <label htmlFor="tax-id">Tax ID</label>
                <input id="tax-id" name="tax_id" maxLength={32} inputMode="numeric" placeholder="Optional Thai tax ID" defaultValue={editingPartner?.tax_id || ""} />
              </div>
              <div className="field">
                <label htmlFor="tax-branch">Tax branch</label>
                <input id="tax-branch" name="tax_branch" maxLength={20} inputMode="numeric" placeholder="00000" defaultValue={editingPartner?.tax_branch || "00000"} />
              </div>
              <div className="field">
                <label htmlFor="partner-email">Email</label>
                <input id="partner-email" name="email" type="email" maxLength={320} placeholder="finance@example.com" defaultValue={editingPartner?.email || ""} />
              </div>
              <div className="field">
                <label htmlFor="partner-phone">Phone</label>
                <input id="partner-phone" name="phone" maxLength={50} placeholder="+66 2 000 0000" defaultValue={editingPartner?.phone || ""} />
              </div>
              <div className="field">
                <label htmlFor="payment-terms">Payment terms (days)</label>
                <input id="payment-terms" name="payment_terms_days" type="number" min={0} max={3650} defaultValue={editingPartner?.payment_terms_days || 0} />
              </div>
              <div className="field">
                <label htmlFor="credit-limit">Credit limit</label>
                <input id="credit-limit" name="credit_limit" type="number" min={0} step="0.01" defaultValue={editingPartner?.credit_limit || "0.00"} />
              </div>
            </div>
            <div className="page-actions">
              <button className="button button-primary" type="submit" disabled={isSaving} aria-busy={isSaving}>
                {formIsEdit ? <Save size={15} aria-hidden="true" /> : <FilePlus2 size={15} aria-hidden="true" />} {isSaving ? "Saving…" : formIsEdit ? "Save partner" : "Create partner"}
              </button>
              <button className="button button-secondary" type="button" disabled={isSaving} onClick={() => { setIsCreateOpen(false); setEditingPartner(null); }}>Cancel</button>
            </div>
          </form>
        </section>
      ) : null}

      <nav className="tab-list" aria-label="Partner sections">
        <a href="/partners" aria-current={!filters.partnerType && !filters.includeArchived ? "page" : undefined} onClick={(event) => handleTab(event, { partnerType: "", includeArchived: false })}>All partners</a>
        <a href="/partners?type=customer" aria-current={filters.partnerType === "customer" ? "page" : undefined} onClick={(event) => handleTab(event, { partnerType: "customer", includeArchived: false })}>Customers</a>
        <a href="/partners?type=vendor" aria-current={filters.partnerType === "vendor" ? "page" : undefined} onClick={(event) => handleTab(event, { partnerType: "vendor", includeArchived: false })}>Vendors</a>
        <a href="/partners?archived=true" aria-current={filters.includeArchived ? "page" : undefined} onClick={(event) => handleTab(event, { partnerType: "", includeArchived: true })}>Archived</a>
      </nav>

      <section className="panel" aria-labelledby="directory-title">
        <div className="section-heading">
          <div className="section-heading-row">
            <div>
              <h2 id="directory-title">Partner directory</h2>
              <p>Tax identity, payment terms and addresses are held at the organization boundary.</p>
            </div>
            <StatusBadge tone="info"><ShieldCheck size={12} aria-hidden="true" /> Tenant scoped</StatusBadge>
          </div>
        </div>
        <form className="workbench-toolbar" aria-label="Partner directory filters" onSubmit={handleSearch}>
          <label className="search-trigger workbench-search" htmlFor="partner-search">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search partners</span>
            <input id="partner-search" type="search" value={draftSearch} onChange={(event) => setDraftSearch(event.target.value)} placeholder="Search by code, name or tax ID" disabled={!canUseWorkspace || viewState === "loading"} />
          </label>
          <label className="visually-hidden" htmlFor="partner-type-filter">Partner type filter</label>
          <select id="partner-type-filter" className="filter-select" aria-label="Partner type filter" value={filters.partnerType} onChange={(event) => {
            const value = event.target.value;
            setFilters((current) => updateFilters(current, { partnerType: isPartnerType(value) ? value : "" }));
          }} disabled={!canUseWorkspace || viewState === "loading"}>
            <option value="">All types</option>
            <option value="customer">Customers</option>
            <option value="vendor">Vendors</option>
            <option value="both">Customer & vendor</option>
          </select>
          <button className="button button-secondary" type="submit" disabled={!canUseWorkspace || viewState === "loading"}>
            <Filter size={15} aria-hidden="true" /> Apply filters
          </button>
        </form>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll partner directory table horizontally" aria-busy={viewState === "loading"}>
          <table className="data-table">
            <caption>Customer and vendor directory</caption>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Partner</th>
                <th scope="col">Type</th>
                <th scope="col">Payment terms</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visiblePartners.length > 0 ? visiblePartners.map((partner) => (
                <tr key={partner.id}>
                  <td><strong>{partner.partner_code}</strong></td>
                  <td><strong>{partner.display_name}</strong>{partner.legal_name ? <small className="table-secondary">{partner.legal_name}</small> : null}</td>
                  <td>{formatPartnerType(partner.partner_type)}</td>
                  <td>{partner.payment_terms_days} days</td>
                  <td><StatusBadge tone={partner.is_active ? "success" : "neutral"}>{partner.is_active ? "Active" : "Archived"}</StatusBadge></td>
                  <td><div className="page-actions"><button className="button button-ghost" type="button" onClick={() => openEdit(partner)}><Pencil size={14} aria-hidden="true" /> Edit</button>{partner.is_active ? <button className="button button-ghost" type="button" onClick={() => { setActionError(""); setArchiveCandidate(partner); }}><Archive size={14} aria-hidden="true" /> Archive</button> : null}</div></td>
                </tr>
              )) : (
                <tr><td className="muted-cell" colSpan={6}>{viewState === "loading" ? "Loading partner records…" : viewState === "error" ? "Partner records unavailable" : viewState === "ready" ? "No partners yet" : "No connected partners"}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {viewState === "ready" && visiblePartners.length === 0 ? (
          <div className="empty-state workbench-empty">
            <span className="empty-state-icon" aria-hidden="true"><ContactRound size={20} /></span>
            <strong>No partners yet</strong>
            <p>Create the first customer or vendor to make it available across controlled sales, purchasing and payment workflows.</p>
            <StatusBadge tone="info"><FilePlus2 size={12} aria-hidden="true" /> Ready to create</StatusBadge>
          </div>
        ) : null}
      </section>

      <div className="panel-grid two-column">
        <section className="panel" aria-labelledby="identity-title">
          <div className="section-heading">
            <h2 id="identity-title">Identity contract</h2>
            <p>Partner records are designed for Thai SME workflows.</p>
          </div>
          <ul className="feature-list">
            <li><ContactRound size={16} aria-hidden="true" /> Customer, vendor or both classifications.</li>
            <li><Building2 size={16} aria-hidden="true" /> Legal name, tax ID and establishment branch.</li>
            <li><Tags size={16} aria-hidden="true" /> Tags and payment terms for operational filtering.</li>
          </ul>
        </section>
        <section className="panel" aria-labelledby="governance-title">
          <div className="section-heading">
            <h2 id="governance-title">Change governance</h2>
            <p>Edits use optimistic versions and append-only audit events.</p>
          </div>
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true"><ShieldCheck size={20} /></span>
            <strong>Partner actions are guarded</strong>
            <p>Every create request carries an idempotency key and remains within the authorized organization scope.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
