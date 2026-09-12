"use client";

import {
  BookOpen,
  Building2,
  Check,
  CircleHelp,
  FileText,
  ReceiptText,
  BarChart3,
  CircleDollarSign,
  Landmark,
  History,
  ScrollText,
  WalletCards,
  LayoutDashboard,
  Menu,
  Moon,
  Percent,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  UsersRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useSyncExternalStore, useState } from "react";

import { ApiError, clearAccessToken, getAccessToken, getApiBaseUrl, getServerApiBaseUrl, subscribeToApiBaseUrl } from "@/lib/api-client";
import { getCurrentUser, signOut, type CurrentUser } from "@/lib/auth";
import {
  WorkspaceAccessProvider,
  WorkspacePermissionBanner,
  type WorkspaceAccess,
  type WorkspaceUserState,
} from "./workspace-context";

type Theme = "dark" | "light";
const THEME_EVENT = "zsme-theme-change";

function subscribeToTheme(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(THEME_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(THEME_EVENT, onStoreChange);
  };
}

function readTheme(): Theme {
  return window.localStorage.getItem("zsme-theme") === "light" ? "light" : "dark";
}

function getServerTheme(): Theme {
  return "dark";
}

function subscribeToHydration() {
  return () => {};
}

function getClientHydration() {
  return true;
}

function getServerHydration() {
  return false;
}

const navigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/partners", label: "Partners", icon: UsersRound },
  { href: "/accounting", label: "Accounting", icon: BookOpen },
  { href: "/sales", label: "Sales & billing", icon: FileText },
  { href: "/invoices", label: "Invoices", icon: ReceiptText },
  { href: "/bills", label: "Vendor bills", icon: ScrollText },
  { href: "/reports", label: "Reports", icon: BarChart3 },
  { href: "/tax", label: "Tax", icon: Percent },
  { href: "/receipts", label: "Receipts", icon: WalletCards },
  { href: "/disbursements", label: "Disbursements", icon: CircleDollarSign },
  { href: "/banking", label: "Banking", icon: Landmark },
  { href: "/audit", label: "Audit", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

const mobileNavigation = [
  navigation[0],
  navigation[3],
  navigation[10],
  navigation[6],
  navigation[12],
] as const;

const pageTitles: Array<{ match: (pathname: string) => boolean; title: string }> = [
  { match: (pathname) => pathname === "/dashboard", title: "Business control center" },
  { match: (pathname) => pathname === "/partners", title: "Customers & vendors" },
  { match: (pathname) => pathname === "/accounting", title: "Accounting workspace" },
  { match: (pathname) => pathname === "/accounting/chart-of-accounts", title: "Chart of accounts" },
  { match: (pathname) => pathname === "/accounting/periods", title: "Fiscal periods" },
  { match: (pathname) => pathname === "/accounting/reconciliation", title: "Reconciliation workspace" },
  { match: (pathname) => pathname === "/sales", title: "Sales & billing" },
  { match: (pathname) => pathname === "/invoices", title: "Sales invoices" },
  { match: (pathname) => pathname === "/bills", title: "Vendor bills" },
  { match: (pathname) => pathname === "/reports" || pathname.startsWith("/reports/"), title: "Reports & insights" },
  { match: (pathname) => pathname === "/tax", title: "Tax configuration" },
  { match: (pathname) => pathname === "/receipts", title: "Customer receipts" },
  { match: (pathname) => pathname === "/disbursements", title: "Vendor disbursements" },
  { match: (pathname) => pathname === "/banking", title: "Banking & reconciliation" },
  { match: (pathname) => pathname === "/audit", title: "Audit & activity" },
  { match: (pathname) => pathname === "/settings", title: "Workspace settings" },
];

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, getServerTheme);
  const isHydrated = useSyncExternalStore(subscribeToHydration, getClientHydration, getServerHydration);
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [userState, setUserState] = useState<WorkspaceUserState>("disconnected");
  const [loadedEndpoint, setLoadedEndpoint] = useState("");
  const [isSigningOut, setIsSigningOut] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const closeNavRef = useRef<HTMLButtonElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const searchTriggerRef = useRef<HTMLButtonElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const closeSearchRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!configuredEndpoint) {
      return undefined;
    }
    let isMounted = true;
    getCurrentUser()
      .then((user) => {
        if (isMounted) {
          setCurrentUser(user);
          setUserState("ready");
          setLoadedEndpoint(configuredEndpoint);
        }
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          if (isMounted) {
            setCurrentUser(null);
            setUserState("error");
            setLoadedEndpoint(configuredEndpoint);
            router.replace("/login");
          }
        } else if (isMounted) {
          setCurrentUser(null);
          setUserState("error");
          setLoadedEndpoint(configuredEndpoint);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [configuredEndpoint, router]);

  useEffect(() => {
    const pageTitle = pageTitles.find(({ match }) => match(pathname))?.title;
    if (pageTitle) {
      document.title = `${pageTitle} | ZSME Enterprise`;
    }
  }, [pathname]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (!isNavOpen) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsNavOpen(false);
        window.requestAnimationFrame(() => menuButtonRef.current?.focus());
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusable = sidebarRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])',
      );
      if (!focusable?.length) {
        event.preventDefault();
        closeNavRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    closeNavRef.current?.focus();
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isNavOpen]);

  useEffect(() => {
    if (!isSearchOpen) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSearchOpen(false);
        window.requestAnimationFrame(() => searchTriggerRef.current?.focus());
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusable = [searchInputRef.current, closeSearchRef.current].filter(
        (element): element is HTMLInputElement | HTMLButtonElement => Boolean(element && !element.disabled),
      );
      if (!focusable.length) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) {
        return;
      }
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.requestAnimationFrame(() => (searchInputRef.current?.disabled ? closeSearchRef.current : searchInputRef.current)?.focus());
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSearchOpen]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    window.localStorage.setItem("zsme-theme", nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.dispatchEvent(new Event(THEME_EVENT));
  };

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await signOut();
    } catch {
      // The local session is still cleared by signOut when the API is unavailable.
    } finally {
      setCurrentUser(null);
      setUserState("disconnected");
      setLoadedEndpoint("");
      setIsSigningOut(false);
      router.replace("/login");
      router.refresh();
    }
  };

  const hasConfiguredSession = Boolean(configuredEndpoint && getAccessToken());
  const sessionLoaded = hasConfiguredSession && loadedEndpoint === configuredEndpoint;
  const effectiveUser = sessionLoaded ? currentUser : null;
  const effectiveUserState: WorkspaceUserState = !hasConfiguredSession
    ? "disconnected"
    : sessionLoaded
      ? userState
      : "loading";

  const accessValue = useMemo<WorkspaceAccess>(
    () => ({
      currentUser: effectiveUser,
      userState: effectiveUserState,
      hasPermission: (permission) => Boolean(
        effectiveUser && (effectiveUser.permissions.includes(permission) || effectiveUser.permissions.includes("*")),
      ),
    }),
    [effectiveUser, effectiveUserState],
  );

  const workspaceLabel = effectiveUser?.organization_id ? "Connected workspace" : "Workspace not connected";
  const operatorLabel = effectiveUser?.display_name || "Operator";

  return (
    <WorkspaceAccessProvider value={accessValue}>
      <div className="app-shell">
      <aside ref={sidebarRef} className={`app-sidebar${isNavOpen ? " is-open" : ""}`} aria-label="Workspace navigation">
        <div className="sidebar-brand">
          <Link className="login-brand" href="/dashboard" aria-label="ZSME dashboard">
            <span className="brand-mark">ZS</span>
            <span className="brand-copy">
              <strong>ZSME</strong>
              <span>Enterprise workspace</span>
            </span>
          </Link>
          <button
            ref={closeNavRef}
            className="sidebar-close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setIsNavOpen(false)}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="sidebar-section-label">Workspace</div>
        <nav id="primary-navigation" className="primary-nav" aria-label="Primary navigation">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              className="nav-link"
              href={href}
              aria-current={isActivePath(pathname, href) ? "page" : undefined}
              onClick={() => setIsNavOpen(false)}
            >
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="workspace-status">
            <ShieldCheck size={16} aria-hidden="true" />
            <p>
              <strong>Governance ready</strong>
              <span>Roles, approvals and audit trails are designed into the workspace.</span>
            </p>
          </div>
          <Link className="button button-ghost" href="/settings">
            <CircleHelp size={15} aria-hidden="true" />
            Platform guidance
          </Link>
        </div>
      </aside>

      {isNavOpen ? (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="Close navigation overlay"
          onClick={() => setIsNavOpen(false)}
        />
      ) : null}

      <div className="app-main">
        <header className="topbar">
          <button
            ref={menuButtonRef}
            className="mobile-menu-button"
            type="button"
            aria-label="Open navigation"
            aria-expanded={isNavOpen}
            onClick={() => setIsNavOpen(true)}
          >
            <Menu size={19} aria-hidden="true" />
          </button>

          <div className="topbar-context" aria-label="Current workspace context">
            <Building2 size={17} aria-hidden="true" />
            <div>
              <strong>{workspaceLabel}</strong>
              <span>Organization-scoped accounting session</span>
            </div>
          </div>

          <div className="topbar-actions">
            <button
              ref={searchTriggerRef}
              className="search-trigger"
              type="button"
              aria-label="Open search"
              aria-controls="search-dialog"
              aria-expanded={isSearchOpen}
              onClick={() => setIsSearchOpen(true)}
            >
              <Search size={16} aria-hidden="true" />
              <span>Search workspace</span>
              <kbd>⌘ K</kbd>
            </button>
            <button
              className="icon-button"
              type="button"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              disabled={!isHydrated}
              onClick={toggleTheme}
            >
              {theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
            </button>
            {effectiveUser ? (
              <button
                className="user-chip"
                type="button"
                aria-label={`Sign out ${operatorLabel}`}
                disabled={isSigningOut}
                onClick={handleSignOut}
              >
                <span className="user-avatar" aria-hidden="true">{operatorLabel.slice(0, 2).toUpperCase()}</span>
                <span>{operatorLabel}</span>
              </button>
            ) : (
              <div className="user-chip" aria-label="Current operator">
              <span className="user-avatar" aria-hidden="true">ZS</span>
              <span>Operator</span>
              </div>
            )}
          </div>
        </header>

        <main id="main-content" className="page-content">
          <WorkspacePermissionBanner pathname={pathname} />
          {children}
        </main>
      </div>

      <nav className="mobile-bottom-nav" aria-label="Mobile navigation">
        {mobileNavigation.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            className="mobile-bottom-nav-link"
            href={href}
            aria-current={isActivePath(pathname, href) ? "page" : undefined}
            onClick={() => setIsNavOpen(false)}
          >
            <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>{label}</span>
          </Link>
        ))}
      </nav>

      {isSearchOpen ? (
        <div
          className="search-backdrop"
          onMouseDown={() => {
            setIsSearchOpen(false);
            window.requestAnimationFrame(() => searchTriggerRef.current?.focus());
          }}
        >
          <section
            id="search-dialog"
            className="search-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="search-dialog-title"
            aria-describedby="search-dialog-description"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="search-dialog-title" className="visually-hidden">Search workspace</h2>
            <div className="search-dialog-header">
              <Search size={18} aria-hidden="true" />
              <input ref={searchInputRef} type="search" aria-label="Search workspace" placeholder="Global search is not available yet" disabled />
              <button
                ref={closeSearchRef}
                className="icon-button"
                type="button"
                aria-label="Close search"
                onClick={() => {
                  setIsSearchOpen(false);
                  window.requestAnimationFrame(() => searchTriggerRef.current?.focus());
                }}
              >
                <X size={17} aria-hidden="true" />
              </button>
            </div>
            <div id="search-dialog-description" className="search-dialog-body">
              <strong>{configuredEndpoint ? "Global search is not enabled in this release." : "Search is available after the API connects."}</strong>
              <span>When enabled, results will respect tenant boundaries and your assigned permissions.</span>
              <span><Check size={14} aria-hidden="true" /> Press Escape to close.</span>
            </div>
          </section>
        </div>
      ) : null}
      </div>
    </WorkspaceAccessProvider>
  );
}
