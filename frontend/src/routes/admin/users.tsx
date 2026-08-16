import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Search, Shield, ShieldOff, Trash2, UserCheck, UserX } from "lucide-react";
import { toast } from "sonner";
import { adminApi, type AdminUser } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/users")({
  head: () => ({ meta: [{ title: "User Management | SS Spark Admin" }] }),
  component: AdminUsersPage,
});

function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 20;

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getUsers({
        skip: page * limit,
        limit,
        search: search || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
      });
      setUsers(res.data);
      setTotal(res.total);
    } catch {
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, roleFilter, statusFilter]);

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); setPage(0); load(); };

  const handleSuspend = async (id: string, email: string) => {
    try {
      await adminApi.suspendUser(id);
      toast.success(`${email} suspended`);
      load();
    } catch { toast.error("Failed to suspend user"); }
  };

  const handleActivate = async (id: string, email: string) => {
    try {
      await adminApi.activateUser(id);
      toast.success(`${email} activated`);
      load();
    } catch { toast.error("Failed to activate user"); }
  };

  const handleDelete = async (id: string, email: string) => {
    if (!confirm(`Delete user ${email}? This is irreversible.`)) return;
    try {
      await adminApi.deleteUser(id);
      toast.success("User deleted");
      load();
    } catch { toast.error("Failed to delete user"); }
  };

  const handleRoleToggle = async (id: string, currentRole: string) => {
    const newRole = currentRole === "admin" ? "user" : "admin";
    try {
      await adminApi.changeRole(id, newRole);
      toast.success(`Role changed to ${newRole}`);
      load();
    } catch { toast.error("Failed to change role"); }
  };

  const statusColor: Record<string, string> = {
    active: "oklch(0.72 0.16 158)",
    suspended: "oklch(0.62 0.21 22)",
    pending_verification: "oklch(0.79 0.16 78)",
  };
  const statusBg: Record<string, string> = {
    active: "oklch(0.72 0.16 158 / 15%)",
    suspended: "oklch(0.62 0.21 22 / 15%)",
    pending_verification: "oklch(0.79 0.16 78 / 15%)",
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>User Management</h1>
        <p className="text-sm text-muted-foreground mt-1">{total} total users</p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <form onSubmit={handleSearch} className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by email or name…"
            className="w-full rounded-xl border bg-card pl-9 pr-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
          />
        </form>
        <select
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
          className="rounded-xl border bg-card px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Roles</option>
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          className="rounded-xl border bg-card px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="pending_verification">Pending</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-border overflow-hidden" style={{ background: "var(--card)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">User</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Role</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Docs</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Questions</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Joined</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 rounded bg-muted animate-pulse" style={{ width: j === 0 ? "140px" : "60px" }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-muted-foreground">No users found.</td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="border-b border-border hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {user.avatar_url ? (
                          <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full object-cover" />
                        ) : (
                          <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold gradient-brand text-brand-foreground">
                            {(user.full_name || user.email)[0].toUpperCase()}
                          </div>
                        )}
                        <div>
                          <p className="font-medium">{user.full_name || "—"}</p>
                          <p className="text-xs text-muted-foreground">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{
                          background: user.role === "admin" ? "color-mix(in oklab, var(--primary) 18%, transparent)" : "var(--secondary)",
                          color: user.role === "admin" ? "var(--primary)" : undefined,
                        }}
                      >
                        {user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{
                          background: statusBg[user.status] ?? statusBg.pending_verification,
                          color: statusColor[user.status] ?? statusColor.pending_verification,
                        }}
                      >
                        {user.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{user.total_documents}</td>
                    <td className="px-4 py-3 text-muted-foreground">{user.total_questions}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleRoleToggle(user.id, user.role)}
                          title={user.role === "admin" ? "Demote to user" : "Promote to admin"}
                          className="p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
                        >
                          <Shield className="h-4 w-4" />
                        </button>
                        {user.status === "suspended" ? (
                          <button
                            onClick={() => handleActivate(user.id, user.email)}
                            title="Activate"
                            className="p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-emerald-400"
                          >
                            <UserCheck className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleSuspend(user.id, user.email)}
                            title="Suspend"
                            className="p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-warning"
                          >
                            <ShieldOff className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(user.id, user.email)}
                          title="Delete"
                          className="p-1.5 rounded-lg hover:bg-destructive/10 transition-colors text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">
              Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-40 hover:bg-accent transition-colors"
              >
                ← Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * limit >= total}
                className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-40 hover:bg-accent transition-colors"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
