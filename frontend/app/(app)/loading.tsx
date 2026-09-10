export default function AppLoading() {
  return (
    <div className="page-stack" aria-busy="true" aria-live="polite">
      <div className="route-loading-header">
        <span className="skeleton skeleton-eyebrow" />
        <span className="skeleton skeleton-title" />
        <span className="skeleton skeleton-subtitle" />
      </div>
      <div className="metric-grid">
        {Array.from({ length: 4 }, (_, index) => <span className="skeleton skeleton-card" key={index} />)}
      </div>
      <section className="panel route-loading-panel">
        <span className="skeleton skeleton-section-title" />
        <span className="skeleton skeleton-row" />
        <span className="skeleton skeleton-row" />
        <span className="skeleton skeleton-row" />
      </section>
      <span className="visually-hidden">Loading workspace</span>
    </div>
  );
}
