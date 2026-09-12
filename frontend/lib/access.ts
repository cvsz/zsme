import { apiRequest } from "@/lib/api-client";

export type AccessRole = {
  id: string;
  name: string;
  permissions: string[];
  is_system: boolean;
};

export type AccessUser = {
  id: string;
  email: string;
  display_name: string;
  organization_id: string | null;
  is_active: boolean;
  roles: AccessRole[];
};

export function listAccessUsers(signal?: AbortSignal): Promise<AccessUser[]> {
  return apiRequest<AccessUser[]>("/v1/access/users", { signal });
}

export function listAccessRoles(signal?: AbortSignal): Promise<AccessRole[]> {
  return apiRequest<AccessRole[]>("/v1/access/roles", { signal });
}

export function replaceAccessUserRoles(
  userId: string,
  roleIds: string[],
): Promise<AccessUser> {
  return apiRequest<AccessUser>(`/v1/access/users/${userId}/roles`, {
    method: "PUT",
    body: JSON.stringify({ role_ids: roleIds }),
  });
}
