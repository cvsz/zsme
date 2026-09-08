import { apiRequest } from "@/lib/api-client";

export type BankAccount = {
  id: string;
  tenant_id: string;
  organization_id: string;
  account_code: string;
  name: string;
  bank_name: string;
  currency_code: string;
  ledger_account_code: string;
  is_active: boolean;
  version: number;
};

export type BankTransaction = {
  id: string;
  tenant_id: string;
  organization_id: string;
  bank_account_id: string;
  import_batch_id: string;
  external_id: string;
  transaction_date: string;
  value_date: string | null;
  description: string;
  reference: string | null;
  amount: string;
  status: "unmatched" | "reconciled";
  matched_payment_id: string | null;
  reconciled_at: string | null;
  version: number;
};

export type BankTransactionImport = {
  external_id: string;
  transaction_date: string;
  value_date?: string;
  description: string;
  reference?: string;
  amount: string;
};

export type BankImportInput = {
  batch_reference: string;
  source_name: string;
  transactions: BankTransactionImport[];
};

export type CreateBankAccountInput = {
  account_code: string;
  name: string;
  bank_name: string;
  currency_code: string;
  ledger_account_code: string;
};

export function listBankAccounts(signal?: AbortSignal): Promise<BankAccount[]> {
  return apiRequest<BankAccount[]>("/v1/banking/accounts", { signal });
}

export function listBankTransactions(
  accountId?: string,
  status?: "unmatched" | "reconciled",
  signal?: AbortSignal,
): Promise<BankTransaction[]> {
  const query = new URLSearchParams();
  if (accountId) {
    query.set("account_id", accountId);
  }
  if (status) {
    query.set("status", status);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<BankTransaction[]>(`/v1/banking/transactions${suffix}`, { signal });
}

export function createBankAccount(
  input: CreateBankAccountInput,
  idempotencyKey: string,
): Promise<BankAccount> {
  return apiRequest<BankAccount>("/v1/banking/accounts", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function importBankTransactions(
  accountId: string,
  input: BankImportInput,
  idempotencyKey: string,
): Promise<{ id: string; transaction_count: number; transactions: BankTransaction[] }> {
  return apiRequest<{ id: string; transaction_count: number; transactions: BankTransaction[] }>(`/v1/banking/accounts/${accountId}/imports`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function reconcileBankTransaction(
  transactionId: string,
  paymentId: string,
  idempotencyKey: string,
): Promise<BankTransaction> {
  return apiRequest<BankTransaction>(`/v1/banking/transactions/${transactionId}/reconcile`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ payment_id: paymentId }),
  });
}

export function createBankingIdempotencyKey(operation: "account" | "import" | "reconcile"): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) {
    throw new Error("Secure randomness is unavailable");
  }
  return `banking-${operation}-${randomId}`;
}
