"use client";

import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ApiConfigurationError, ApiError } from "@/lib/api-client";
import { signIn } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage("");
    setIsSubmitting(true);
    const formData = new FormData(event.currentTarget);
    try {
      await signIn({
        tenant_slug: String(formData.get("tenant_slug") || ""),
        email: String(formData.get("email") || ""),
        password: String(formData.get("password") || ""),
      });
      router.replace("/dashboard");
      router.refresh();
    } catch (error) {
      if (error instanceof ApiConfigurationError) {
        setMessage("Authentication service is not connected in this environment. No credentials were sent.");
      } else if (error instanceof ApiError) {
        setMessage(error.status === 401 ? "Sign-in failed. Check your workspace and account details." : "Sign-in could not be completed. Try again or contact an administrator.");
      } else {
        setMessage("The authentication service could not be reached. No session was created.");
      }
    } finally {
      setIsSubmitting(false);
    }
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
            {message ? <p className="form-message" role="status" aria-live="polite">{message}</p> : null}
            <button className="button button-primary" type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
              <LockKeyhole size={15} aria-hidden="true" />
              {isSubmitting ? "Signing in…" : "Sign in"}
              {!isSubmitting ? <ArrowRight size={15} aria-hidden="true" /> : null}
            </button>
          </form>

          <p className="login-footnote">Need access? Contact your workspace administrator. Authentication and session management are server-owned.</p>
        </section>
      </main>
    </div>
  );
}
