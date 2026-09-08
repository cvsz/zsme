import { apiRequest } from "@/lib/api-client";

export type PartnerType = "customer" | "vendor" | "both";

export type PartnerAddress = {
  id: string;
  partner_id: string;
  address_type: "registered" | "billing" | "shipping" | "other";
  label: string | null;
  address_line1: string;
  address_line2: string | null;
  district: string | null;
  province: string | null;
  postal_code: string | null;
  country_code: string;
  is_primary: boolean;
};

export type Partner = {
  id: string;
  tenant_id: string;
  organization_id: string;
  partner_code: string;
  partner_type: PartnerType;
  display_name: string;
  legal_name: string | null;
  tax_id: string | null;
  tax_branch: string;
  email: string | null;
  phone: string | null;
  payment_terms_days: number;
  credit_limit: string;
  is_active: boolean;
  version: number;
  tags: string[];
  addresses: PartnerAddress[];
};

export type PartnerListFilters = {
  partnerType?: PartnerType;
  search?: string;
  includeArchived?: boolean;
};

export type CreatePartnerInput = {
  partner_code: string;
  partner_type: PartnerType;
  display_name: string;
  tax_id?: string;
  tax_branch?: string;
  email?: string;
  phone?: string;
  payment_terms_days?: number;
};

export function listPartners(
  filters: PartnerListFilters = {},
  signal?: AbortSignal,
): Promise<Partner[]> {
  const query = new URLSearchParams();
  if (filters.partnerType) {
    query.set("type", filters.partnerType);
  }
  if (filters.search?.trim()) {
    query.set("search", filters.search.trim());
  }
  if (filters.includeArchived) {
    query.set("include_archived", "true");
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<Partner[]>(`/v1/partners${suffix}`, { signal });
}

export function createPartner(
  input: CreatePartnerInput,
  idempotencyKey: string,
): Promise<Partner> {
  return apiRequest<Partner>("/v1/partners", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function createPartnerIdempotencyKey(): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) {
    throw new Error("Secure randomness is unavailable");
  }
  return `partner-create-${randomId}`;
}
