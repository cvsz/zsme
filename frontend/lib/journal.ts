import { apiRequest } from "@/lib/api-client";

export type JournalLine = {
  id: string;
  line_no: number;
  account_code: string;
  debit: string;
  credit: string;
  memo: string | null;
};

export type JournalEntry = {
  id: string;
  tenant_id: string;
  organization_id: string;
  fiscal_period_id: string | null;
  reference: string;
  journal_date: string;
  memo: string | null;
  status: "posted";
  source_type: string | null;
  source_id: string | null;
  reversal_of_id: string | null;
  posted_at: string | null;
  created_at: string;
  lines: JournalLine[];
  total_debit: string;
  total_credit: string;
};

export type JournalEntryPage = {
  items: JournalEntry[];
  limit: number;
  offset: number;
  total: number;
  next_offset: number | null;
};

export type JournalLineInput = {
  account_code: string;
  debit: string;
  credit: string;
  memo?: string;
};

export type PostJournalInput = {
  reference: string;
  memo?: string;
  journal_date: string;
  source_type: string;
  lines: JournalLineInput[];
};

export type JournalPostResult = {
  entry_id: string;
  status: "posted" | "already_posted";
  total: string;
  audit_event_id: string;
};

export function listJournalEntries(
  filters: { reference?: string; fromDate?: string; toDate?: string; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<JournalEntryPage> {
  const query = new URLSearchParams();
  if (filters.reference?.trim()) query.set("reference", filters.reference.trim());
  if (filters.fromDate) query.set("from_date", filters.fromDate);
  if (filters.toDate) query.set("to_date", filters.toDate);
  query.set("limit", String(filters.limit ?? 50));
  query.set("offset", String(filters.offset ?? 0));
  return apiRequest<JournalEntryPage>(`/v1/accounting/journal-entries?${query.toString()}`, { signal });
}

export function postJournalEntry(input: PostJournalInput, idempotencyKey: string): Promise<JournalPostResult> {
  return apiRequest<JournalPostResult>("/v1/accounting/journal-entries", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function reverseJournalEntry(
  entryId: string,
  idempotencyKey: string,
  reversalDate?: string,
): Promise<JournalPostResult> {
  const query = reversalDate ? `?reversal_date=${encodeURIComponent(reversalDate)}` : "";
  return apiRequest<JournalPostResult>(`/v1/accounting/journal-entries/${entryId}/reverse${query}`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function createJournalIdempotencyKey(operation: "post" | "reverse"): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) throw new Error("Secure randomness is unavailable");
  return `journal-${operation}-${randomId}`;
}

