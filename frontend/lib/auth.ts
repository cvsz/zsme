import {
  apiRequest,
  clearAccessToken,
  setAccessToken,
} from "@/lib/api-client";

export type LoginInput = {
  tenant_slug: string;
  email: string;
  password: string;
};

export type SessionResponse = {
  expires_in: number;
  csrf_token: string;
};

export type CurrentUser = {
  user_id: string;
  tenant_id: string;
  organization_id: string | null;
  organization_currency: string | null;
  organization_timezone: string | null;
  email: string;
  display_name: string;
  roles: string[];
  permissions: string[];
};

export async function signIn(input: LoginInput): Promise<SessionResponse> {
  const session = await apiRequest<SessionResponse>("/v1/auth/browser-login", {
    method: "POST",
    body: JSON.stringify(input),
    authenticated: false,
  });
  setAccessToken("", session.csrf_token);
  return session;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/v1/auth/me").then((user) => {
    setAccessToken("");
    return user;
  });
}

export async function signOut(): Promise<void> {
  try {
    await apiRequest<void>("/v1/auth/logout", { method: "POST" });
  } finally {
    clearAccessToken();
  }
}
