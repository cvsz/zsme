"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import Link from "next/link";

export default function AppError({ reset }: Readonly<{ error: Error & { digest?: string }; reset: () => void }>) {
  return (
    <section className="route-error" role="alert" aria-labelledby="route-error-title">
      <span className="empty-state-icon" aria-hidden="true"><AlertTriangle size={22} /></span>
      <p className="eyebrow">Workspace error</p>
      <h1 id="route-error-title" className="page-title">This workspace surface could not load.</h1>
      <p className="page-subtitle">No financial action was submitted. Try the page again or return to the dashboard.</p>
      <div className="page-actions">
        <button className="button button-primary" type="button" onClick={reset}><RefreshCw size={15} aria-hidden="true" /> Try again</button>
        <Link className="button button-secondary" href="/dashboard">Return to dashboard</Link>
      </div>
    </section>
  );
}
