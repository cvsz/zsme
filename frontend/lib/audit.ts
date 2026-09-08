import { apiRequest } from "@/lib/api-client";

export type AuditEvent = {
  id: string;
  tenant_id: string;
  organization_id: string | null;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  correlation_id: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AuditEventPage = {
  items: AuditEvent[];
  limit: number;
  offset: number;
  total: number;
  next_offset: number | null;
};

export type AuditEventFilters = {
  action?: string;
  entityType?: string;
  limit?: number;
  offset?: number;
};

export function listAuditEvents(
  filters: AuditEventFilters = {},
  signal?: AbortSignal,
): Promise<AuditEventPage> {
  const query = new URLSearchParams();
  if (filters.action?.trim()) {
    query.set("action", filters.action.trim());
  }
  if (filters.entityType?.trim()) {
    query.set("entity_type", filters.entityType.trim());
  }
  query.set("limit", String(filters.limit || 50));
  query.set("offset", String(filters.offset || 0));
  return apiRequest<AuditEventPage>(`/v1/audit/events?${query.toString()}`, { signal });
}

export function exportAuditEvents(events: AuditEvent[]): void {
  const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), events }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "zsme-audit-events.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
