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
  head: () => ({ meta: [{ title: "Admin Console | SS Spark" }] }),
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
          <div className="h-8 w-48 rounded-xl bg-slate-900/60" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-32 rounded-2xl bg-slate-900/40" />
            ))}
          </div>
          <div className="h-64 rounded-2xl bg-slate-900/40" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 sm:p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight font-display">
            System Intelligence Console
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">Platform metrics, telemetry, and vector store health</p>
        </div>
        <button
          onClick={() => loadData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-900/60 px-3.5 py-2 text-xs font-medium text-slate-200 hover:border-sky-400/40 hover:bg-slate-800/80 transition-all cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin text-sky-400" : ""}`} />
          Refresh Metrics
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Users"
          value={stats?.total_users ?? 0}
          subtitle={`${stats?.new_users_last_7_days ?? 0} new this week`}
          icon={<Users className="h-4 w-4" />}
          trend={{ value: 12, label: "vs last month" }}
          color="#38bdf8"
        />
        <StatsCard
          title="Active Users"
          value={stats?.active_users ?? 0}
          icon={<Zap className="h-4 w-4" />}
          color="#34d399"
        />
        <StatsCard
          title="Documents"
          value={stats?.total_documents ?? 0}
          icon={<FileText className="h-4 w-4" />}
          color="#818cf8"
        />
        <StatsCard
          title="Questions Asked"
          value={stats?.total_questions ?? 0}
          icon={<MessageSquare className="h-4 w-4" />}
          color="#38bdf8"
        />
        <StatsCard
          title="Chat Sessions"
          value={stats?.total_sessions ?? 0}
          icon={<Bot className="h-4 w-4" />}
          color="#a78bfa"
        />
        <StatsCard
          title="Storage Used"
          value={`${((stats?.total_storage_mb ?? 0) / 1024).toFixed(2)} GB`}
          icon={<HardDrive className="h-4 w-4" />}
          color="#f43f5e"
        />
        <StatsCard
          title="Indexed Chunks"
          value={health?.chromadb?.chunk_count ?? 0}
          icon={<Database className="h-4 w-4" />}
          color="#60a5fa"
        />
        <StatsCard
          title="PaperQA Docs"
          value={health?.paperqa?.indexed_documents ?? 0}
          icon={<Server className="h-4 w-4" />}
          color="#34d399"
        />
      </div>

      {/* Charts + Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity chart */}
        <div className="lg:col-span-2 relative overflow-hidden rounded-2xl border border-white/5 bg-[rgba(9,15,30,0.65)] p-5 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-mono font-medium tracking-wider text-slate-400 uppercase">
              Platform Query & Upload Volume (30 Days)
            </h3>
            <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_6px_#38bdf8]" />Questions</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-indigo-400 shadow-[0_0_6px_#818cf8]" />Uploads</span>
            </div>
          </div>
          {activity.length > 0 ? (
            <ResponsiveContainer width="100%" height={230}>
              <AreaChart data={activity}>
                <defs>
                  <linearGradient id="qGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="uGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false}
                       tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(10, 16, 32, 0.95)",
                    border: "1px solid rgba(56, 189, 248, 0.2)",
                    borderRadius: "12px",
                    fontSize: "12px",
                    color: "#f8fafc",
                    boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
                  }}
                />
                <Area type="monotone" dataKey="questions" stroke="#38bdf8"
                      fill="url(#qGrad)" strokeWidth={2} dot={false} name="Questions" />
                <Area type="monotone" dataKey="uploads" stroke="#818cf8"
                      fill="url(#uGrad)" strokeWidth={2} dot={false} name="Uploads" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-52 text-xs font-mono text-slate-500">
              No activity telemetry recorded yet.
            </div>
          )}
        </div>

        {/* System health & Quick Links */}
        <div className="space-y-6">
          <SystemHealth items={healthItems} />

          {/* Quick links */}
          <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-[rgba(9,15,30,0.65)] p-5 backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.5)]">
            <h3 className="text-xs font-mono font-medium tracking-wider text-slate-400 uppercase mb-3">
              Direct Controls
            </h3>
            <div className="space-y-1.5">
              {[
                { href: "/admin/users", label: "User Directory", icon: Users },
                { href: "/admin/documents", label: "Document Registry", icon: FileText },
                { href: "/admin/analytics", label: "Deep Analytics", icon: BarChart3 },
                { href: "/admin/logs", label: "System Telemetry Logs", icon: MessageSquare },
              ].map(({ href, label, icon: Icon }) => (
                <a key={href} href={href}
                   className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800/60 hover:text-sky-300 transition-colors">
                  <Icon className="h-3.5 w-3.5 text-sky-400" />
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
