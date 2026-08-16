import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw, Search } from "lucide-react";
import { adminApi, type AuditLog } from "@/lib/admin-api";
import { toast } from "sonner";

export const Route = createFileRoute("/admin/logs")({
  head: () => ({ meta: [{ title: "Audit Logs | SS Spark Admin" }] }),
  component: AdminLogsPage,
});

const ACTION_COLORS: Record<string, string> = {
  login: "oklch(0.72 0.16 158)",
  login_failed: "oklch(0.62 0.21 22)",
  logout: "var(--muted-foreground)",
  register: "oklch(0.68 0.22 45)",
  email_verified: "oklch(0.72 0.16 158)",
  password_reset: "oklch(0.79 0.16 78)",
  upload: "oklch(0.76 0.19 60)",
  delete_document: "oklch(0.62 0.21 22)",
  admin_action: "oklch(0.79 0.16 78)",
  suspend: "oklch(0.62 0.21 22)",
  activate: "oklch(0.72 0.16 158)",
  role_change: "oklch(0.68 0.22 45)",
};

function AdminLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const limit = 50;

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getLogs({
        action: actionFilter || undefined,
        skip: page * limit,
        limit,
      });
      setLogs(res.data);
      setTotal(res.total);
    } catch {
      toast.error("Failed to load logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, actionFilter]);

  const uniqueActions = ["login", "login_failed", "logout", "register", "upload", "delete_document", "admin_action", "suspend", "activate", "role_change"];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Audit Logs</h1>
          <p className="text-sm text-muted-foreground mt-1">{total} total entries (90-day retention)</p>
        </div>
        <button onClick={() => load()}
                className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm hover:bg-accent transition-colors">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(0); }}
          className="rounded-xl border bg-card px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Actions</option>
          {uniqueActions.map((a) => (
            <option key={a} value={a}>{a.replace(/_/g, " ")}</option>
          ))}
        </select>
      </div>

      {/* Logs table */}
      <div className="rounded-2xl border border-border overflow-hidden" style={{ background: "var(--card)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Time</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Action</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Detail</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">User ID</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">IP</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 rounded bg-muted animate-pulse" style={{ width: ["80px", "80px", "200px", "140px", "80px"][j] }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-muted-foreground">No logs found.</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="border-b border-border hover:bg-accent/20 transition-colors">
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-full px-2 py-0.5 text-xs font-medium"
                            style={{
                              background: `${ACTION_COLORS[log.action] ?? "oklch(0.71 0.028 274)"} / 15%`,
                              color: ACTION_COLORS[log.action] ?? "oklch(0.71 0.028 274)",
                            }}>
                        {log.action.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs max-w-xs truncate">{log.detail}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{log.user_id?.slice(0, 8) ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{log.ip_address ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {total > limit && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</p>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-40 hover:bg-accent transition-colors">← Prev</button>
              <button onClick={() => setPage((p) => p + 1)} disabled={(page + 1) * limit >= total}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-40 hover:bg-accent transition-colors">Next →</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
