import { apiRequest } from "@/lib/api-client";

export type DocumentKind = "invoice" | "bill";
export type DocumentStatus = "draft" | "posted" | "void";

export type DocumentLine = {
  id: string;
  document_id: string;
  line_no: number;
  description: string;
  quantity: string;
  unit_price: string;
  tax_rate: string;
  net_amount: string;
  tax_amount: string;
  total_amount: string;
  account_code: string;
};

export type FinancialDocument = {
  id: string;
  tenant_id: string;
  organization_id: string;
  document_type: "sales_invoice" | "vendor_bill";
  document_number: string;
  partner_id: string;
  issue_date: string;
  due_date: string;
  currency_code: string;
  control_account_code: string;
  tax_account_code: string | null;
  memo: string | null;
  subtotal: string;
  tax_total: string;
  total: string;
  status: DocumentStatus;
  ledger_entry_id: string | null;
  posted_at: string | null;
  version: number;
  lines: DocumentLine[];
};

export type DocumentListFilters = {
  status?: DocumentStatus;
  search?: string;
};

export type CreateDocumentInput = {
  document_number: string;
  partner_id: string;
  issue_date: string;
  due_date: string;
  currency_code: string;
  control_account_code: string;
  tax_account_code?: string;
  memo?: string;
  lines: Array<{
    description: string;
    quantity: string;
    unit_price: string;
    tax_rate: string;
    account_code: string;
  }>;
};

function pathFor(kind: DocumentKind): string {
  return kind === "invoice" ? "/v1/ar/invoices" : "/v1/ap/bills";
}

export function listDocuments(
  kind: DocumentKind,
  filters: DocumentListFilters = {},
  signal?: AbortSignal,
): Promise<FinancialDocument[]> {
  const query = new URLSearchParams();
  if (filters.status) {
    query.set("status", filters.status);
  }
  if (filters.search?.trim()) {
    query.set("search", filters.search.trim());
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<FinancialDocument[]>(`${pathFor(kind)}${suffix}`, { signal });
}

export function createDocument(
  kind: DocumentKind,
  input: CreateDocumentInput,
  idempotencyKey: string,
): Promise<FinancialDocument> {
  return apiRequest<FinancialDocument>(pathFor(kind), {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function postDocument(
  kind: DocumentKind,
  documentId: string,
  idempotencyKey: string,
): Promise<FinancialDocument> {
  return apiRequest<FinancialDocument>(`${pathFor(kind)}/${documentId}/post`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function createDocumentIdempotencyKey(operation: "create" | "post"): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) {
    throw new Error("Secure randomness is unavailable");
  }
  return `document-${operation}-${randomId}`;
}

export function formatMoney(value: string, currency = "THB"): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return `${currency} —`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}
