import type { LucideIcon } from "lucide-react";

import { StatusBadge } from "./status-badge";

type DataCardProps = {
  label: string;
  value: string;
  meta: string;
  status?: string;
  icon: LucideIcon;
};

export function DataCard({ label, value, meta, status = "Awaiting API", icon: Icon }: DataCardProps) {
  return (
    <article className="data-card">
      <div className="data-card-header">
        <span className="data-card-label">{label}</span>
        <span className="data-card-icon" aria-hidden="true">
          <Icon size={16} strokeWidth={1.8} />
        </span>
      </div>
      <strong className="data-card-value">{value}</strong>
      <div className="data-card-meta">
        <span>{meta}</span>
        <StatusBadge tone="warning">{status}</StatusBadge>
      </div>
    </article>
  );
}
