"use client";

import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import { createContext, useContext } from "react";

import type { CurrentUser } from "@/lib/auth";

export type WorkspaceUserState = "disconnected" | "loading" | "ready" | "error";

export type WorkspaceAccess = {
  currentUser: CurrentUser | null;
  userState: WorkspaceUserState;
  hasPermission: (permission: string) => boolean;
};

const defaultAccess: WorkspaceAccess = {
  currentUser: null,
  userState: "disconnected",
  hasPermission: () => false,
};

const WorkspaceAccessContext = createContext<WorkspaceAccess>(defaultAccess);

export function WorkspaceAccessProvider({
  value,
  children,
}: Readonly<{ value: WorkspaceAccess; children: React.ReactNode }>) {
  return <WorkspaceAccessContext.Provider value={value}>{children}</WorkspaceAccessContext.Provider>;
}

export function useWorkspaceAccess(): WorkspaceAccess {
  return useContext(WorkspaceAccessContext);
}

type RouteAccess = {
  permission: string;
  surface: string;
};

const routeAccess: Array<{ match: (pathname: string) => boolean; access: RouteAccess }> = [
  { match: (pathname) => pathname === "/dashboard", access: { permission: "dashboard:read", surface: "dashboard metrics" } },
  { match: (pathname) => pathname === "/partners" || pathname.startsWith("/partners/"), access: { permission: "partner:read", surface: "partner records" } },
  { match: (pathname) => pathname === "/accounting" || pathname.startsWith("/accounting/"), access: { permission: "accounting:read", surface: "accounting controls" } },
  { match: (pathname) => pathname === "/sales" || pathname.startsWith("/sales/"), access: { permission: "ar:read", surface: "sales operations" } },
  { match: (pathname) => pathname === "/invoices" || pathname.startsWith("/invoices/"), access: { permission: "ar:read", surface: "sales invoices" } },
  { match: (pathname) => pathname === "/bills" || pathname.startsWith("/bills/"), access: { permission: "ap:read", surface: "vendor bills" } },
  { match: (pathname) => pathname === "/reports" || pathname.startsWith("/reports/"), access: { permission: "reports:read", surface: "financial reports" } },
  { match: (pathname) => pathname === "/tax" || pathname.startsWith("/tax/"), access: { permission: "tax:read", surface: "tax configuration" } },
  { match: (pathname) => pathname === "/receipts" || pathname.startsWith("/receipts/"), access: { permission: "ar:read", surface: "receipts" } },
  { match: (pathname) => pathname === "/disbursements" || pathname.startsWith("/disbursements/"), access: { permission: "ap:read", surface: "vendor disbursements" } },
  { match: (pathname) => pathname === "/banking" || pathname.startsWith("/banking/"), access: { permission: "banking:read", surface: "banking and reconciliation" } },
  { match: (pathname) => pathname === "/audit" || pathname.startsWith("/audit/"), access: { permission: "audit:read", surface: "audit evidence" } },
];

export function getRouteAccess(pathname: string): RouteAccess | null {
  return routeAccess.find(({ match }) => match(pathname))?.access ?? null;
}

export function WorkspacePermissionBanner({ pathname }: Readonly<{ pathname: string }>) {
  const { currentUser, userState, hasPermission } = useWorkspaceAccess();
  const access = getRouteAccess(pathname);

  if (userState !== "ready" || !currentUser || !access || hasPermission(access.permission)) {
    return null;
  }

  return (
    <section className="permission-banner" role="alert" aria-labelledby="permission-banner-title">
      <span className="permission-banner-icon" aria-hidden="true">
        <LockKeyhole size={18} />
      </span>
      <div>
        <strong id="permission-banner-title">Access restricted</strong>
        <p>Your role does not include permission to review {access.surface}. Ask a workspace administrator to update your access.</p>
      </div>
      <Link className="button button-secondary" href="/settings#access">
        Review access
      </Link>
    </section>
  );
}
