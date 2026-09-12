import { apiRequest } from "@/lib/api-client";

export type WorkspaceSearchKind =
  | "partner"
  | "invoice"
  | "bill"
  | "receipt"
  | "disbursement"
  | "journal"
  | "bank_transaction";

export type WorkspaceSearchResult = {
  kind: WorkspaceSearchKind;
  id: string;
  label: string;
  meta: string;
  href: string;
};

type WorkspaceSearchResponse = {
  items: WorkspaceSearchResult[];
};

export async function searchWorkspace(
  query: string,
  signal?: AbortSignal,
): Promise<WorkspaceSearchResult[]> {
  const normalized = query.trim();
  if (normalized.length < 2) {
    return [];
  }
  const response = await apiRequest<WorkspaceSearchResponse>(
    `/v1/search?q=${encodeURIComponent(normalized)}&limit=20`,
    { signal },
  );
  return response.items;
}
