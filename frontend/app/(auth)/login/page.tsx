"use client";

import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const [message, setMessage] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage("Authentication service is not connected in this environment. No credentials were sent.");
  };

  return (
    <div className="login-layout">
      <aside className="login-aside">
        <div className="login-aside-copy">
          <span className="brand-mark">ZS</span>
          <h1>Confident control for growing businesses.</h1>
          <p>Thailand-first finance operations with strong accounting boundaries, clear approvals and an interface your team can trust.</p>
          <div className="workspace-status">
            <ShieldCheck size={18} aria-hidden="true" />
            <p><strong>Enterprise controls by default</strong><span>Tenant isolation, immutable posting and audit-ready events.</span></p>
          </div>
        </div>
      </aside>

      <main className="login-main">
        <section className="login-card" aria-labelledby="login-title">
          <div className="login-header">
            <Link className="login-brand" href="/dashboard" aria-label="ZSME home">
              <span className="brand-mark">ZS</span>
              <span>ZSME Enterprise</span>
            </Link>
            <div>
              <h1 id="login-title">Sign in to your workspace</h1>
              <p>Use your organization account to continue.</p>
            </div>
          </div>

          <form className="form-grid" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="tenant-slug">Workspace slug</label>
              <input id="tenant-slug" name="tenant_slug" type="text" autoComplete="organization" placeholder="your-workspace" required />
              <small>Your tenant boundary is checked before access is granted.</small>
            </div>
            <div className="field">
              <label htmlFor="email">Work email</label>
              <input id="email" name="email" type="email" autoComplete="email" placeholder="name@company.com" required />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete="current-password" placeholder="Enter your password" required />
            </div>
            {message ? <p className="form-message" role="status">{message}</p> : null}
            <button className="button button-primary" type="submit">
              <LockKeyhole size={15} aria-hidden="true" />
              Sign in
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </form>

          <p className="login-footnote">Need access? Contact your workspace administrator. Authentication and session management are server-owned.</p>
        </section>
      </main>
    </div>
  );
}
