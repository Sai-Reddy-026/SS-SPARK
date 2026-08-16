import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  BarChart3, Bell, Bot, ChevronLeft, ChevronRight, FileText, Home,
  LogOut, MessageSquare, Settings, Shield, Upload, Users,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

const NAV_ITEMS = [
  { path: "/admin", label: "Dashboard", icon: Home },
  { path: "/admin/users", label: "Users", icon: Users },
  { path: "/admin/documents", label: "Documents", icon: FileText },
  { path: "/admin/analytics", label: "Analytics", icon: BarChart3 },
  { path: "/admin/ai-monitoring", label: "AI Monitoring", icon: Bot },
  { path: "/admin/logs", label: "Logs", icon: MessageSquare },
  { path: "/admin/notifications", label: "Notifications", icon: Bell },
  { path: "/admin/settings", label: "Settings", icon: Settings },
];

interface AdminSidebarProps {
  currentPath?: string;
}

export function AdminSidebar({ currentPath = "" }: AdminSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    toast.success("Logged out");
    navigate({ to: "/login" });
  };

  return (
    <aside
      className="flex flex-col h-full border-r border-border transition-all duration-300 relative"
      style={{
        width: collapsed ? "64px" : "240px",
        background: "var(--sidebar)",
        minWidth: collapsed ? "64px" : "240px",
      }}
    >
      {/* Toggle button */}
      <button
        onClick={() => setCollapsed((p) => !p)}
        className="absolute -right-3 top-6 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background text-muted-foreground shadow-sm hover:text-foreground transition-colors"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </button>

      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-border">
        <div className="flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-lg gradient-brand">
          <Shield className="h-4 w-4 text-brand-foreground" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-sm font-bold truncate" style={{ fontFamily: "var(--font-display)" }}>
              SS Spark
            </p>
            <p className="text-xs text-muted-foreground">Admin Panel</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-2">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
            const active = currentPath === path || (path !== "/admin" && currentPath.startsWith(path));
            return (
              <li key={path}>
                <Link
                  to={path as any}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all"
                  style={{
                    background: active ? "color-mix(in oklab, var(--primary) 18%, transparent)" : "transparent",
                    color: active ? "var(--primary)" : undefined,
                    fontWeight: active ? "600" : undefined,
                  }}
                  title={collapsed ? label : undefined}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  {!collapsed && <span className="truncate">{label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer: user + logout */}
      <div className="border-t border-border p-3">
        {!collapsed && user && (
          <div className="flex items-center gap-2 mb-3 px-1">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt={user.full_name} className="h-7 w-7 rounded-full object-cover" />
            ) : (
              <div className="h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold gradient-brand text-brand-foreground">
                {(user.full_name || user.email || "A").charAt(0).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-xs font-medium truncate">{user.full_name || user.email}</p>
              <p className="text-xs text-muted-foreground">Administrator</p>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          {!collapsed && "Logout"}
        </button>
      </div>
    </aside>
  );
}
