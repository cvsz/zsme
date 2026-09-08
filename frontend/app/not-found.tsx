import Link from "next/link";

export default function NotFound() {
  return (
    <main className="not-found">
      <div className="not-found-content">
        <p className="eyebrow">404 · Not found</p>
        <h1 className="page-title">That workspace route does not exist.</h1>
        <p className="page-subtitle">Return to the command center or ask an administrator to confirm your access.</p>
        <Link className="button button-primary" href="/dashboard">Return to dashboard</Link>
      </div>
    </main>
  );
}
