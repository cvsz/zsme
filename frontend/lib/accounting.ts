import { apiRequest } from "@/lib/api-client";

export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";

export type ChartAccount = {
  id: string;
  tenant_id: string;
  organization_id: string;
  code: string;
  name: string;
  account_type: AccountType;
  parent_id: string | null;
  is_control: boolean;
  is_cash_equivalent: boolean;
  is_active: boolean;
  version: number;
};

export type FiscalPeriodStatus = "open" | "locked";

export type FiscalPeriod = {
  id: string;
  tenant_id: string;
  organization_id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: FiscalPeriodStatus;
  locked_at: string | null;
  version: number;
};

export type CreateChartAccountInput = {
  code: string;
  name: string;
  account_type: AccountType;
  parent_id?: string;
  is_control?: boolean;
  is_cash_equivalent?: boolean;
};

export type UpdateChartAccountInput = {
  expected_version: number;
  name?: string;
  parent_id?: string | null;
  is_control?: boolean;
  is_cash_equivalent?: boolean;
  is_active?: boolean;
};

export type CreateFiscalPeriodInput = {
  name: string;
  start_date: string;
  end_date: string;
};

export function listChartAccounts(signal?: AbortSignal): Promise<ChartAccount[]> {
  return apiRequest<ChartAccount[]>("/v1/accounting/accounts", { signal });
}

export function createChartAccount(
  input: CreateChartAccountInput,
  idempotencyKey: string,
): Promise<ChartAccount> {
  return apiRequest<ChartAccount>("/v1/accounting/accounts", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function updateChartAccount(
  accountId: string,
  input: UpdateChartAccountInput,
  idempotencyKey: string,
): Promise<ChartAccount> {
  return apiRequest<ChartAccount>(`/v1/accounting/accounts/${accountId}`, {
    method: "PATCH",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function listFiscalPeriods(signal?: AbortSignal): Promise<FiscalPeriod[]> {
  return apiRequest<FiscalPeriod[]>("/v1/accounting/periods", { signal });
}

export function createFiscalPeriod(
  input: CreateFiscalPeriodInput,
  idempotencyKey: string,
): Promise<FiscalPeriod> {
  return apiRequest<FiscalPeriod>("/v1/accounting/periods", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function lockFiscalPeriod(periodId: string, idempotencyKey: string): Promise<FiscalPeriod> {
  return apiRequest<FiscalPeriod>(`/v1/accounting/periods/${periodId}/lock`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function createAccountingIdempotencyKey(
  operation: "account-create" | "account-update" | "period-create" | "period-lock",
): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) {
    throw new Error("Secure randomness is unavailable");
  }
  return `accounting-${operation}-${randomId}`;
}

