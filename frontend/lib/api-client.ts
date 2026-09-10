const API_BASE_URL_KEY = "zsme-api-base-url";
const ACCESS_TOKEN_KEY = "zsme-access-token";
const API_BASE_URL_EVENT = "zsme-api-base-url-change";
const customApiEndpointAllowed =
  process.env.NEXT_PUBLIC_ALLOW_CUSTOM_API_ENDPOINT === "true" ||
  (process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_ALLOW_CUSTOM_API_ENDPOINT !== "false");

export type ProblemDetails = {
  code?: string;
  detail?: string;
  correlation_id?: string;
  fields?: Array<{ field: string; message: string; type: string }>;
};

export class ApiConfigurationError extends Error {
  constructor(message = "API endpoint is not configured") {
    super(message);
    this.name = "ApiConfigurationError";
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly correlationId?: string;
  readonly fields?: ProblemDetails["fields"];

  constructor(status: number, problem: ProblemDetails) {
    super(problem.detail || "The API request failed");
    this.name = "ApiError";
    this.status = status;
    this.code = problem.code;
    this.correlationId = problem.correlation_id;
    this.fields = problem.fields;
  }
}

function normalizeApiBaseUrl(value: string): string {
  const normalized = value.trim().replace(/\/+$/, "");
  if (!normalized) {
    return "";
  }
  let parsed: URL;
  try {
    parsed = new URL(normalized);
  } catch {
    throw new ApiConfigurationError("API endpoint must be a valid URL");
  }
  if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) {
    throw new ApiConfigurationError("API endpoint must use HTTP or HTTPS");
  }
  const allowInsecureCustomEndpoint =
    customApiEndpointAllowed && process.env.NEXT_PUBLIC_ALLOW_INSECURE_CUSTOM_API_ENDPOINT === "true";
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:" && !allowInsecureCustomEndpoint) {
    throw new ApiConfigurationError("Production API endpoints must use HTTPS");
  }
  if (parsed.username || parsed.password || parsed.hash) {
    throw new ApiConfigurationError("API endpoint must not include credentials or a fragment");
  }
  return normalized;
}

export function getApiBaseUrl(): string {
  const configured = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
  if (configured) {
    try {
      return normalizeApiBaseUrl(configured);
    } catch {
      return "";
    }
  }
  if (typeof window === "undefined") {
    return "";
  }
  if (!customApiEndpointAllowed) {
    return "";
  }
  try {
    return normalizeApiBaseUrl(window.localStorage.getItem(API_BASE_URL_KEY) || "");
  } catch {
    return "";
  }
}

export function isApiBaseUrlManaged(): boolean {
  return Boolean((process.env.NEXT_PUBLIC_API_BASE_URL || "").trim());
}

export function isApiEndpointUserConfigurable(): boolean {
  return customApiEndpointAllowed && !isApiBaseUrlManaged();
}

export function getServerApiBaseUrl(): string {
  const configured = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
  try {
    return normalizeApiBaseUrl(configured);
  } catch {
    return "";
  }
}

export function subscribeToApiBaseUrl(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(API_BASE_URL_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(API_BASE_URL_EVENT, onStoreChange);
  };
}

export function setApiBaseUrl(value: string): string {
  if (!customApiEndpointAllowed && value.trim()) {
    throw new ApiConfigurationError("API endpoint is managed by the deployment environment");
  }
  const normalized = normalizeApiBaseUrl(value);
  if (typeof window !== "undefined") {
    if (normalized) {
      window.localStorage.setItem(API_BASE_URL_KEY, normalized);
    } else {
      window.localStorage.removeItem(API_BASE_URL_KEY);
    }
    window.dispatchEvent(new Event(API_BASE_URL_EVENT));
  }
  return normalized;
}

export function getAccessToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.sessionStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

export function setAccessToken(token: string): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
  }
}

export function clearAccessToken(): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  }
}

async function problemFromResponse(response: Response): Promise<ProblemDetails> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object") {
      return body as ProblemDetails;
    }
  } catch {
    // Keep network and proxy failures safe and user-readable.
  }
  return { detail: `Request failed with status ${response.status}` };
}

type ApiRequestOptions = RequestInit & { authenticated?: boolean };

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { authenticated = true, ...requestInit } = options;
  const baseUrl = getApiBaseUrl();
  if (!baseUrl) {
    throw new ApiConfigurationError();
  }

  const headers = new Headers(requestInit.headers);
  headers.set("Accept", "application/json");
  if (requestInit.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated) {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${baseUrl}${path}`, { ...requestInit, headers });
  if (!response.ok) {
    throw new ApiError(response.status, await problemFromResponse(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function checkApiHealth(): Promise<{ status: string; database?: string }> {
  return apiRequest<{ status: string; database?: string }>("/ready", { authenticated: false });
}

export { API_BASE_URL_KEY, ACCESS_TOKEN_KEY };
