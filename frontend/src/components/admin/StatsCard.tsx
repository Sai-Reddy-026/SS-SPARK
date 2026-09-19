import { type ReactNode } from "react";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  trend?: { value: number; label: string };
  color?: string;
}

export function StatsCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  color = "rgb(56, 189, 248)",
}: StatsCardProps) {
  const isPositive = (trend?.value ?? 0) >= 0;

  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-white/5 bg-[rgba(9,15,30,0.65)] p-5 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-sky-400/30 hover:shadow-[0_12px_32px_rgba(0,0,0,0.7),0_0_24px_rgba(56,189,248,0.12)] shadow-[0_8px_24px_rgba(0,0,0,0.5)]"
    >
      {/* Specular highlight */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.12) 30%, rgba(56,189,248,0.3) 50%, rgba(255,255,255,0.12) 70%, transparent 100%)",
        }}
      />

      <div className="flex items-start justify-between mb-4">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 shadow-sm"
          style={{ background: "rgba(56, 189, 248, 0.1)", color }}
        >
          {icon}
        </div>
        {trend && (
          <span
            className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-mono font-medium border"
            style={{
              background: isPositive ? "rgba(16, 185, 129, 0.12)" : "rgba(244, 63, 94, 0.12)",
              color: isPositive ? "rgb(52, 211, 153)" : "rgb(251, 113, 133)",
              borderColor: isPositive ? "rgba(16, 185, 129, 0.25)" : "rgba(244, 63, 94, 0.25)",
            }}
          >
            {isPositive ? "↑" : "↓"} {Math.abs(trend.value)}%
          </span>
        )}
      </div>

      <p className="text-3xl font-bold mb-1 text-white tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
        {typeof value === "number" && value > 1000
          ? value >= 1_000_000
            ? `${(value / 1_000_000).toFixed(1)}M`
            : `${(value / 1_000).toFixed(1)}K`
          : value}
      </p>
      <p className="text-xs font-medium text-slate-400">{title}</p>
      {subtitle && <p className="text-[11px] text-slate-500 mt-1 font-mono">{subtitle}</p>}
      {trend && <p className="text-[11px] text-slate-500 mt-1">{trend.label}</p>}
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
    ok: "rgb(52, 211, 153)",
    error: "rgb(251, 113, 133)",
    warning: "rgb(251, 191, 36)",
    loading: "rgb(148, 163, 184)",
  };
  const statusBg = {
    ok: "rgba(16, 185, 129, 0.12)",
    error: "rgba(244, 63, 94, 0.12)",
    warning: "rgba(245, 158, 11, 0.12)",
    loading: "rgba(148, 163, 184, 0.12)",
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-[rgba(9,15,30,0.65)] p-5 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
      {/* Specular highlight */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.12) 30%, rgba(56,189,248,0.3) 50%, rgba(255,255,255,0.12) 70%, transparent 100%)",
        }}
      />
      <h3 className="text-xs font-mono font-medium tracking-wider text-slate-400 uppercase mb-4">
        Infrastructure Telemetry
      </h3>
      <div className="space-y-3">
        {items.map(({ name, status, detail }) => (
          <div key={name} className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div
                className="h-2 w-2 rounded-full shadow-sm"
                style={{ background: statusColor[status], boxShadow: `0 0 8px ${statusColor[status]}` }}
              />
              <span className="text-xs font-medium text-slate-200">{name}</span>
            </div>
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-mono font-medium border border-white/5"
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
