import { apiRequest } from "@/lib/api-client";

export type TrialBalanceRow = {
  account_code: string;
  account_name: string | null;
  account_type: string | null;
  debit: string;
  credit: string;
  balance: string;
};

export type TrialBalanceReport = {
  from_date: string;
  to_date: string;
  rows: TrialBalanceRow[];
  total_debit: string;
  total_credit: string;
};

export function getTrialBalance(
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<TrialBalanceReport> {
  const query = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiRequest<TrialBalanceReport>(`/v1/reports/trial-balance?${query.toString()}`, { signal });
}

