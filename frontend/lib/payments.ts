import { apiRequest } from "@/lib/api-client";

export type PaymentKind = "receipt" | "disbursement";
export type PaymentStatus = "draft" | "posted" | "void";

export type PaymentAllocation = {
  id: string;
  payment_id: string;
  document_id: string;
  amount: string;
};

export type PaymentRecord = {
  id: string;
  tenant_id: string;
  organization_id: string;
  payment_type: "receipt" | "disbursement";
  payment_number: string;
  partner_id: string;
  payment_date: string;
  currency_code: string;
  amount: string;
  cash_account_code: string;
  unapplied_account_code: string | null;
  memo: string | null;
  status: PaymentStatus;
  ledger_entry_id: string | null;
  posted_at: string | null;
  version: number;
  allocations: PaymentAllocation[];
};

export type PaymentListFilters = { status?: PaymentStatus };

export type CreatePaymentInput = {
  payment_number: string;
  partner_id: string;
  payment_date: string;
  currency_code: string;
  amount: string;
  cash_account_code: string;
  unapplied_account_code?: string;
  memo?: string;
  allocations: Array<{ document_id: string; amount: string }>;
};

function pathFor(kind: PaymentKind): string {
  return kind === "receipt" ? "/v1/ar/receipts" : "/v1/ap/disbursements";
}

export function listPayments(
  kind: PaymentKind,
  filters: PaymentListFilters = {},
  signal?: AbortSignal,
): Promise<PaymentRecord[]> {
  const query = new URLSearchParams();
  if (filters.status) {
    query.set("status", filters.status);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<PaymentRecord[]>(`${pathFor(kind)}${suffix}`, { signal });
}

export function createPayment(
  kind: PaymentKind,
  input: CreatePaymentInput,
  idempotencyKey: string,
): Promise<PaymentRecord> {
  return apiRequest<PaymentRecord>(pathFor(kind), {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function postPayment(
  kind: PaymentKind,
  paymentId: string,
  idempotencyKey: string,
): Promise<PaymentRecord> {
  return apiRequest<PaymentRecord>(`${pathFor(kind)}/${paymentId}/post`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function createPaymentIdempotencyKey(operation: "create" | "post"): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) {
    throw new Error("Secure randomness is unavailable");
  }
  return `payment-${operation}-${randomId}`;
}
