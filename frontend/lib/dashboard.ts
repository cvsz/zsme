import { apiRequest } from "@/lib/api-client";

export type DashboardActivity = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  correlation_id: string;
  created_at: string;
};

export type DashboardSummary = {
  organization_id: string;
  as_of: string;
  currency_code: string;
  cash_position: string | null;
  receivables: string;
  payables: string;
  open_invoices: number;
  open_bills: number;
  customer_count: number;
  vendor_count: number;
  unmatched_bank_transactions: number;
  recent_activity: DashboardActivity[];
};

export function getDashboardSummary(asOf: string, signal?: AbortSignal): Promise<DashboardSummary> {
  const query = new URLSearchParams({ as_of: asOf });
  return apiRequest<DashboardSummary>(`/v1/dashboard/summary?${query.toString()}`, { signal });
}

export function formatDashboardMoney(value: string | null, currency: string): string {
  if (value === null) {
    return "—";
  }
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return `${currency} —`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: 2 }).format(amount);
}

