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

export type AccountReportRow = {
  account_code: string;
  account_name: string | null;
  amount: string;
};

export type ProfitLossReport = {
  from_date: string;
  to_date: string;
  rows: AccountReportRow[];
  total_revenue: string;
  total_expenses: string;
  net_income: string;
};

export type BalanceSheetReport = {
  as_of: string;
  assets: AccountReportRow[];
  liabilities: AccountReportRow[];
  equity: AccountReportRow[];
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  net_income: string;
  total_liabilities_and_equity: string;
};

export type GeneralLedgerRow = {
  entry_id: string;
  reference: string;
  journal_date: string;
  account_code: string;
  memo: string | null;
  source_type: string | null;
  debit: string;
  credit: string;
};

export type GeneralLedgerReport = {
  from_date: string;
  to_date: string;
  rows: GeneralLedgerRow[];
  total_debit: string;
  total_credit: string;
};

export type AgedBucket = "current" | "1_30" | "31_60" | "61_90" | "over_90";

export type AgedDocumentRow = {
  document_id: string;
  document_number: string;
  partner_id: string;
  issue_date: string;
  due_date: string;
  total: string;
  allocated: string;
  outstanding: string;
  bucket: AgedBucket;
};

export type AgedReport = {
  as_of: string;
  document_type: "sales_invoice" | "vendor_bill";
  rows: AgedDocumentRow[];
  bucket_totals: Record<AgedBucket, string>;
  current_total: string;
  overdue_total: string;
  total_outstanding: string;
};

export function getTrialBalance(
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<TrialBalanceReport> {
  const query = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiRequest<TrialBalanceReport>(`/v1/reports/trial-balance?${query.toString()}`, { signal });
}

export function getProfitLoss(
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<ProfitLossReport> {
  const query = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiRequest<ProfitLossReport>(`/v1/reports/profit-loss?${query.toString()}`, { signal });
}

export function getBalanceSheet(asOf: string, signal?: AbortSignal): Promise<BalanceSheetReport> {
  const query = new URLSearchParams({ as_of: asOf });
  return apiRequest<BalanceSheetReport>(`/v1/reports/balance-sheet?${query.toString()}`, { signal });
}

export function getGeneralLedger(
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<GeneralLedgerReport> {
  const query = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiRequest<GeneralLedgerReport>(`/v1/reports/general-ledger?${query.toString()}`, { signal });
}

export function getAgedReceivable(asOf: string, signal?: AbortSignal): Promise<AgedReport> {
  const query = new URLSearchParams({ as_of: asOf });
  return apiRequest<AgedReport>(`/v1/reports/aged-receivable?${query.toString()}`, { signal });
}

export function getAgedPayable(asOf: string, signal?: AbortSignal): Promise<AgedReport> {
  const query = new URLSearchParams({ as_of: asOf });
  return apiRequest<AgedReport>(`/v1/reports/aged-payable?${query.toString()}`, { signal });
}
