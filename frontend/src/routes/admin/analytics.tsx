import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  AreaChart, Area, BarChart, Bar, CartesianGrid, PieChart, Pie, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis, Legend,
} from "recharts";
import { adminApi } from "@/lib/admin-api";
import type { GlobalStats } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/analytics")({
  head: () => ({ meta: [{ title: "Analytics | SS Spark Admin" }] }),
  component: AdminAnalyticsPage,
});

const COLORS = [
  "oklch(0.68 0.22 45)",
  "oklch(0.76 0.19 60)",
  "oklch(0.72 0.16 158)",
  "oklch(0.82 0.15 75)",
  "oklch(0.62 0.18 35)",
];

function AdminAnalyticsPage() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [activity, setActivity] = useState<Array<{ date: string; questions: number; uploads: number }>>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [statsRes, activityRes] = await Promise.all([
        adminApi.getStats(),
        adminApi.getActivity(days),
      ]);
      setStats(statsRes.data);
      setActivity(activityRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [days]);

  const pieData = stats
    ? [
        { name: "Active Users", value: stats.active_users },
        { name: "Inactive", value: stats.total_users - stats.active_users },
      ]
    : [];

  const summaryCards = stats
    ? [
        { label: "Avg Docs / User", value: (stats.total_documents / Math.max(stats.total_users, 1)).toFixed(1) },
        { label: "Avg Q / User", value: (stats.total_questions / Math.max(stats.total_users, 1)).toFixed(1) },
        { label: "Storage / User (MB)", value: (stats.total_storage_mb / Math.max(stats.total_users, 1)).toFixed(2) },
        { label: "New Users (7d)", value: stats.new_users_last_7_days },
      ]
    : [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">Platform usage metrics and trends</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-xl border bg-card px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Summary row */}
      {!loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards.map(({ label, value }) => (
            <div key={label} className="rounded-2xl border border-border p-4 text-center" style={{ background: "var(--card)" }}>
              <p className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>{value}</p>
              <p className="text-xs text-muted-foreground mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 rounded-2xl bg-muted animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* Activity area chart */}
          <div className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
            <h3 className="text-sm font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
              Daily Activity — Questions & Uploads
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={activity}>
                <defs>
                  <linearGradient id="ag1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="oklch(0.68 0.22 45)" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="oklch(0.68 0.22 45)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ag2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="oklch(0.76 0.19 60)" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="oklch(0.76 0.19 60)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} axisLine={false}
                       tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "12px", fontSize: "12px" }} />
                <Legend />
                <Area type="monotone" dataKey="questions" stroke="oklch(0.68 0.22 45)" fill="url(#ag1)" strokeWidth={2} dot={false} name="Questions" />
                <Area type="monotone" dataKey="uploads" stroke="oklch(0.76 0.19 60)" fill="url(#ag2)" strokeWidth={2} dot={false} name="Uploads" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Bar chart */}
            <div className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
              <h3 className="text-sm font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
                Daily Questions vs Uploads
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={activity.slice(-14)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v) => v.slice(5)} />
                  <YAxis tick={{ fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "12px", fontSize: "12px" }} />
                  <Bar dataKey="questions" fill="oklch(0.68 0.22 45)" radius={[4, 4, 0, 0]} name="Questions" />
                  <Bar dataKey="uploads" fill="oklch(0.76 0.19 60)" radius={[4, 4, 0, 0]} name="Uploads" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* User distribution pie */}
            <div className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
              <h3 className="text-sm font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
                User Status Distribution
              </h3>
              {pieData.some((d) => d.value > 0) ? (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90}
                         paddingAngle={4} dataKey="value" nameKey="name">
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "12px", fontSize: "12px" }} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">No user data yet.</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
