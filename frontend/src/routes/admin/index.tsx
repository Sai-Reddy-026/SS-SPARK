import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  BarChart3, Bot, Database, FileText, HardDrive, MessageSquare,
  RefreshCw, Server, Users, Zap,
} from "lucide-react";
import {
  AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { StatsCard, SystemHealth } from "@/components/admin/StatsCard";
import { adminApi, type GlobalStats, type SystemHealth as HealthType } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/")({
  head: () => ({ meta: [{ title: "Admin Dashboard | SS Spark" }] }),
  component: AdminDashboard,
});

function AdminDashboard() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [activity, setActivity] = useState<Array<{ date: string; questions: number; uploads: number }>>([]);
  const [health, setHealth] = useState<HealthType | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const [statsRes, activityRes, healthRes] = await Promise.all([
        adminApi.getStats(),
        adminApi.getActivity(30),
        adminApi.getSystemHealth(),
      ]);
      setStats(statsRes.data);
      setActivity(activityRes.data);
      setHealth(healthRes.data);
    } catch (err) {
      console.error("Failed to load admin data:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const healthItems = health
    ? [
        { name: "MongoDB", status: health.mongodb.status as "ok" | "error", detail: health.mongodb.database ?? health.mongodb.error },
        { name: "ChromaDB", status: health.chromadb.status as "ok" | "error", detail: health.chromadb.chunk_count ? `${health.chromadb.chunk_count} chunks` : health.chromadb.error },
        { name: "PaperQA", status: health.paperqa.status as "ok" | "error", detail: `${health.paperqa.indexed_documents} docs indexed` },
        { name: "API Server", status: "ok" as const, detail: "Running" },
      ]
    : Array.from({ length: 4 }, (_, i) => ({
        name: ["MongoDB", "ChromaDB", "PaperQA", "API Server"][i],
        status: "loading" as const,
      }));

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 rounded-lg bg-muted" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-32 rounded-2xl bg-muted" />
            ))}
          </div>
          <div className="h-64 rounded-2xl bg-muted" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>
            Admin Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Platform overview and system health</p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm hover:bg-accent transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Users"
          value={stats?.total_users ?? 0}
          subtitle={`${stats?.new_users_last_7_days ?? 0} new this week`}
          icon={<Users className="h-5 w-5" />}
          trend={{ value: 12, label: "vs last month" }}
          color="oklch(0.68 0.22 45)"
        />
        <StatsCard
          title="Active Users"
          value={stats?.active_users ?? 0}
          icon={<Zap className="h-5 w-5" />}
          color="oklch(0.72 0.16 158)"
        />
        <StatsCard
          title="Documents"
          value={stats?.total_documents ?? 0}
          icon={<FileText className="h-5 w-5" />}
          color="oklch(0.76 0.19 60)"
        />
        <StatsCard
          title="Questions Asked"
          value={stats?.total_questions ?? 0}
          icon={<MessageSquare className="h-5 w-5" />}
          color="oklch(0.68 0.22 45)"
        />
        <StatsCard
          title="Chat Sessions"
          value={stats?.total_sessions ?? 0}
          icon={<Bot className="h-5 w-5" />}
          color="oklch(0.68 0.22 45)"
        />
        <StatsCard
          title="Storage Used"
          value={`${((stats?.total_storage_mb ?? 0) / 1024).toFixed(2)} GB`}
          icon={<HardDrive className="h-5 w-5" />}
          color="oklch(0.62 0.21 22)"
        />
        <StatsCard
          title="Indexed Chunks"
          value={health?.chromadb?.chunk_count ?? 0}
          icon={<Database className="h-5 w-5" />}
          color="oklch(0.76 0.19 60)"
        />
        <StatsCard
          title="PaperQA Docs"
          value={health?.paperqa?.indexed_documents ?? 0}
          icon={<Server className="h-5 w-5" />}
          color="oklch(0.72 0.16 158)"
        />
      </div>

      {/* Charts + Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity chart */}
        <div className="lg:col-span-2 rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold" style={{ fontFamily: "var(--font-display)" }}>
              Platform Activity (30 days)
            </h3>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: "oklch(0.68 0.22 45)" }} />Questions</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: "oklch(0.76 0.19 60)" }} />Uploads</span>
            </div>
          </div>
          {activity.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={activity}>
                <defs>
                  <linearGradient id="qGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="oklch(0.68 0.22 45)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="oklch(0.68 0.22 45)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="uGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="oklch(0.76 0.19 60)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="oklch(0.76 0.19 60)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} axisLine={false}
                       tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)", border: "1px solid var(--border)",
                    borderRadius: "12px", fontSize: "12px",
                  }}
                />
                <Area type="monotone" dataKey="questions" stroke="oklch(0.68 0.22 45)"
                      fill="url(#qGrad)" strokeWidth={2} dot={false} name="Questions" />
                <Area type="monotone" dataKey="uploads" stroke="oklch(0.76 0.19 60)"
                      fill="url(#uGrad)" strokeWidth={2} dot={false} name="Uploads" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-52 text-sm text-muted-foreground">
              No activity data yet.
            </div>
          )}
        </div>

        {/* System health */}
        <div className="space-y-4">
          <SystemHealth items={healthItems} />

          {/* Quick links */}
          <div className="rounded-2xl border border-border p-4" style={{ background: "var(--card)" }}>
            <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: "var(--font-display)" }}>Quick Actions</h3>
            <div className="space-y-2">
              {[
                { href: "/admin/users", label: "Manage Users", icon: Users },
                { href: "/admin/documents", label: "View Documents", icon: FileText },
                { href: "/admin/analytics", label: "Full Analytics", icon: BarChart3 },
                { href: "/admin/logs", label: "System Logs", icon: MessageSquare },
              ].map(({ href, label, icon: Icon }) => (
                <a key={href} href={href}
                   className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-accent transition-colors">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  {label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
