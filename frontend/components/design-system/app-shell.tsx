"use client";

import {
  BookOpen,
  Building2,
  Check,
  ChevronDown,
  CircleHelp,
  FileText,
  LayoutDashboard,
  Menu,
  Moon,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useSyncExternalStore, useState } from "react";

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
  { href: "/accounting", label: "Accounting", icon: BookOpen },
  { href: "/sales", label: "Sales & billing", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, getServerTheme);
  const isHydrated = useSyncExternalStore(subscribeToHydration, getClientHydration, getServerHydration);
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (!isSearchOpen) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSearchOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSearchOpen]);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    window.localStorage.setItem("zsme-theme", nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.dispatchEvent(new Event(THEME_EVENT));
  };

  return (
    <div className="app-shell">
      <aside className={`app-sidebar${isNavOpen ? " is-open" : ""}`}>
        <div className="sidebar-brand">
          <Link className="login-brand" href="/dashboard" aria-label="ZSME dashboard">
            <span className="brand-mark">ZS</span>
            <span className="brand-copy">
              <strong>ZSME</strong>
              <span>Enterprise workspace</span>
            </span>
          </Link>
          <button
            className="sidebar-close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setIsNavOpen(false)}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="sidebar-section-label">Workspace</div>
        <nav className="primary-nav" aria-label="Primary navigation">
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
              <strong>Workspace not connected</strong>
              <span>Fiscal year 2026 · THB</span>
            </div>
            <ChevronDown size={14} aria-hidden="true" />
          </div>

          <div className="topbar-actions">
            <button
              className="search-trigger"
              type="button"
              aria-label="Open search"
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
            <div className="user-chip" aria-label="Current operator">
              <span className="user-avatar" aria-hidden="true">ZS</span>
              <span>Operator</span>
            </div>
          </div>
        </header>

        <main id="main-content" className="page-content">
          {children}
        </main>
      </div>

      {isSearchOpen ? (
        <div className="search-backdrop" role="presentation" onMouseDown={() => setIsSearchOpen(false)}>
          <section
            className="search-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="search-dialog-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="search-dialog-title" className="visually-hidden">Search workspace</h2>
            <div className="search-dialog-header">
              <Search size={18} aria-hidden="true" />
              <input autoFocus type="search" placeholder="Search transactions, customers or settings" />
              <button className="icon-button" type="button" aria-label="Close search" onClick={() => setIsSearchOpen(false)}>
                <X size={17} aria-hidden="true" />
              </button>
            </div>
            <div className="search-dialog-body">
              <strong>Search will be available when the API is connected.</strong>
              <span>Results will respect tenant boundaries and your assigned permissions.</span>
              <span><Check size={14} aria-hidden="true" /> Press Escape to close.</span>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
