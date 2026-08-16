import { type ReactNode } from "react";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  trend?: { value: number; label: string };
  color?: string;
}

export function StatsCard({ title, value, subtitle, icon, trend, color = "oklch(0.68 0.22 45)" }: StatsCardProps) {
  const isPositive = (trend?.value ?? 0) >= 0;

  return (
    <div
      className="rounded-2xl border border-border p-5 transition-all hover-lift"
      style={{ background: "var(--card)" }}
    >
      <div className="flex items-start justify-between mb-4">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ background: `${color} / 15%`, color }}
        >
          {icon}
        </div>
        {trend && (
          <span
            className="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
            style={{
              background: isPositive ? "oklch(0.72 0.16 158 / 15%)" : "oklch(0.62 0.21 22 / 15%)",
              color: isPositive ? "oklch(0.72 0.16 158)" : "oklch(0.62 0.21 22)",
            }}
          >
            {isPositive ? "↑" : "↓"} {Math.abs(trend.value)}%
          </span>
        )}
      </div>

      <p className="text-3xl font-bold mb-1" style={{ fontFamily: "var(--font-display)" }}>
        {typeof value === "number" && value > 1000
          ? value >= 1_000_000
            ? `${(value / 1_000_000).toFixed(1)}M`
            : `${(value / 1_000).toFixed(1)}K`
          : value}
      </p>
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
      {trend && <p className="text-xs text-muted-foreground mt-1">{trend.label}</p>}
    </div>
  );
}

// -------------------------------------------------------------------------- //
// System Health Card
// -------------------------------------------------------------------------- //

interface HealthItem {
  name: string;
  status: "ok" | "error" | "warning" | "loading";
  detail?: string;
}

export function SystemHealth({ items }: { items: HealthItem[] }) {
  const statusColor = {
    ok: "oklch(0.72 0.16 158)",
    error: "oklch(0.62 0.21 22)",
    warning: "oklch(0.79 0.16 78)",
    loading: "oklch(0.71 0.028 274)",
  };
  const statusBg = {
    ok: "oklch(0.72 0.16 158 / 15%)",
    error: "oklch(0.62 0.21 22 / 15%)",
    warning: "oklch(0.79 0.16 78 / 15%)",
    loading: "oklch(0.71 0.028 274 / 15%)",
  };

  return (
    <div className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
      <h3 className="text-sm font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
        System Health
      </h3>
      <div className="space-y-3">
        {items.map(({ name, status, detail }) => (
          <div key={name} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className="h-2 w-2 rounded-full"
                style={{ background: statusColor[status] }}
              />
              <span className="text-sm">{name}</span>
            </div>
            <span
              className="rounded-full px-2 py-0.5 text-xs font-medium"
              style={{ background: statusBg[status], color: statusColor[status] }}
            >
              {detail ?? status.toUpperCase()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
