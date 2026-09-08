import { apiRequest } from "@/lib/api-client";

export type TaxType = "vat" | "withholding";

export type TaxRateRule = {
  id: string;
  tenant_id: string;
  organization_id: string;
  tax_type: TaxType;
  code: string;
  name: string;
  rate: string;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  version: number;
};

export type CreateTaxRateInput = {
  tax_type: TaxType;
  code: string;
  name: string;
  rate: string;
  effective_from: string;
  effective_to?: string;
};

export function listTaxRates(taxType?: TaxType, signal?: AbortSignal): Promise<TaxRateRule[]> {
  const query = taxType ? `?tax_type=${encodeURIComponent(taxType)}` : "";
  return apiRequest<TaxRateRule[]>(`/v1/tax/rates${query}`, { signal });
}

export function createTaxRate(input: CreateTaxRateInput, idempotencyKey: string): Promise<TaxRateRule> {
  return apiRequest<TaxRateRule>("/v1/tax/rates", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function createTaxRateIdempotencyKey(): string {
  let randomId = globalThis.crypto?.randomUUID?.();
  if (!randomId && globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    randomId = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  if (!randomId) throw new Error("Secure randomness is unavailable");
  return `tax-rate-create-${randomId}`;
}

