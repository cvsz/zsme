"use client";

import {
  Banknote,
  CircleAlert,
  FileText,
  Plus,
  Receipt,
  RefreshCw,
  ShieldCheck,
  Users,
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
import { formatMoney, listDocuments, type FinancialDocument } from "@/lib/documents";
import { listPartners, type Partner } from "@/lib/partners";

type LoadState = "idle" | "ready" | "error";

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function safeError(error: unknown): string {
  if (error instanceof ApiConfigurationError) return "Connect the API endpoint before loading sales operations.";
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your role cannot review sales operations in this organization.";
  }
  return "Sales data is unavailable. Retry the request or review the API connection.";
}

export default function SalesPage() {
  const configuredEndpoint = useSyncExternalStore(subscribeToApiBaseUrl, getApiBaseUrl, getServerApiBaseUrl);
  const [invoices, setInvoices] = useState<FinancialDocument[]>([]);
  const [customers, setCustomers] = useState<Partner[]>([]);
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
    Promise.all([
      listDocuments("invoice", {}, controller.signal),
      listPartners({ partnerType: "customer" }, controller.signal),
    ])
      .then(([invoiceResult, customerResult]) => {
        if (!controller.signal.aborted) {
          setInvoices(invoiceResult);
          setCustomers(customerResult);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setInvoices([]);
          setCustomers([]);
          setLoadError(safeError(error));
          setLoadState("error");
        }
      });
    return () => controller.abort();
  }, [configuredEndpoint, refreshNonce]);

  const partnerNames = new Map(customers.map((customer) => [customer.id, customer.display_name]));
  const postedInvoices = invoices.filter((invoice) => invoice.status === "posted");
  const grossInvoiceValue = invoices.reduce((sum, invoice) => sum + Number(invoice.total), 0);
  const statusLabel = viewState === "ready" ? `${invoices.length} invoice${invoices.length === 1 ? "" : "s"} loaded` : viewState === "loading" ? "Loading sales data" : viewState === "error" ? "Data unavailable" : viewState === "unauthenticated" ? "Sign-in required" : "API not connected";
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  return (
    <div className="page-stack">
      <header className="page-header"><div className="page-header-copy"><p className="eyebrow">Revenue operations</p><h1 className="page-title">Sales & billing</h1><p className="page-subtitle">Coordinate customer master data, invoice issuance and collections from one governed operational surface.</p></div><div className="page-actions"><StatusBadge tone={statusTone}>{statusLabel}</StatusBadge><Link className="button button-primary" href="/invoices?create=1"><Plus size={15} aria-hidden="true" /> Create invoice</Link></div></header>

      {viewState !== "ready" ? <section className="connection-banner" aria-label={viewState === "error" ? "Sales data needs attention" : "Sales connection status"} role={viewState === "error" ? "alert" : undefined}><div className="connection-banner-copy"><Receipt size={19} aria-hidden="true" /><div><strong>{viewState === "error" ? "Sales data needs attention" : "Sales operations stay guarded until the workspace connects"}</strong><p>{viewState === "disconnected" ? "Connect the API to load authorized customer and invoice data. No financial values are fabricated." : viewState === "unauthenticated" ? "Sign in with an organization account before reviewing sales activity." : viewState === "error" ? loadError : "Customer identity and invoice totals are loaded from tenant-scoped server contracts."}</p></div></div><div className="page-actions">{viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setInvoices([]); setCustomers([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry sales load</button> : null}{viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}</div></section> : null}

      <section className="metric-grid" aria-label="Sales metrics"><DataCard label="Posted invoices" value={viewState === "ready" ? String(postedInvoices.length) : "—"} meta="Ledger-backed revenue documents" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={Receipt} /><DataCard label="Gross invoice value" value={viewState === "ready" ? formatMoney(grossInvoiceValue.toFixed(2)) : "—"} meta="Visible invoice register" status={viewState === "ready" ? "Source data" : "Awaiting API"} icon={Banknote} /><DataCard label="Customers" value={viewState === "ready" ? String(customers.length) : "—"} meta="Active organization partners" status={viewState === "ready" ? "Current" : "Awaiting API"} icon={Users} /><DataCard label="Collection health" value={viewState === "ready" ? "Review" : "—"} meta="Settlement status requires receipts" status={viewState === "ready" ? "Open receipts" : "Not evaluated"} icon={ShieldCheck} /></section>

      <section className="panel" aria-label="Sales invoice register" aria-labelledby="sales-invoices-title"><div className="section-heading"><div className="section-heading-row"><div><h2 id="sales-invoices-title">Invoice register</h2><p>Customer and payment records are shown only after tenant authorization succeeds.</p></div><StatusBadge tone="info"><ShieldCheck size={12} aria-hidden="true" /> Tenant isolation</StatusBadge></div></div><div className="data-table-wrap" tabIndex={0} aria-label="Scroll sales invoice table horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Sales invoice register</caption><thead><tr><th scope="col">Invoice</th><th scope="col">Customer</th><th scope="col">Issue date</th><th scope="col">Due date</th><th scope="col">Total</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead><tbody>{invoices.length > 0 ? invoices.map((invoice) => <tr key={invoice.id}><td><strong>{invoice.document_number}</strong><small className="table-secondary">{invoice.currency_code}</small></td><td>{partnerNames.get(invoice.partner_id) || "Authorized customer"}</td><td>{formatDate(invoice.issue_date)}</td><td>{formatDate(invoice.due_date)}</td><td>{formatMoney(invoice.total, invoice.currency_code)}</td><td>{invoice.status === "posted" ? <StatusBadge tone="success">Posted</StatusBadge> : invoice.status === "draft" ? <StatusBadge tone="warning">Draft</StatusBadge> : <StatusBadge tone="neutral">Void</StatusBadge>}</td><td><Link className="button button-ghost" href="/invoices">Open invoice</Link></td></tr>) : <tr><td className="muted-cell" colSpan={7}>{viewState === "loading" ? "Loading invoices…" : viewState === "error" ? "Invoices unavailable" : viewState === "ready" ? "No invoices to display" : "No connected invoices"}</td></tr>}</tbody></table></div>{viewState === "ready" && invoices.length === 0 ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><CircleAlert size={20} /></span><strong>No invoices to display</strong><p>Create a draft invoice for an active customer, then post it after review.</p><Link className="button button-secondary" href="/invoices?create=1">Create first invoice</Link></div> : null}</section>
    </div>
  );
}
