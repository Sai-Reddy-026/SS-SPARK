import { memo, useMemo } from "react";
import { Link } from "@tanstack/react-router";
import {
  ChevronLeft,
  FileText,
  ImageIcon,
  MessageSquarePlus,
  PanelLeftOpen,
  Search,
  Settings,
  Shield,
  History,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { formatTime, type UploadedDoc } from "@/lib/analyzer";
import { useAuth } from "@/lib/auth";
import { SparkCore } from "@/components/astra/SparkCore";

export interface SidebarChat {
  id: string;
  title: string;
  subtitle?: string;
}

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  docs: UploadedDoc[];
  chats?: SidebarChat[];
  activeChat: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onUpload: () => void;
  onOpenSettings?: () => void;
  search: string;
  onSearch: (value: string) => void;
}

export const AnalyzerSidebar = memo(function AnalyzerSidebar({
  open,
  onToggle,
  docs,
  chats = [],
  activeChat,
  onSelectChat,
  onNewChat,
  onUpload,
  onOpenSettings,
  search,
  onSearch,
}: SidebarProps) {
  const { user, isGuest, isAuthenticated } = useAuth();

  // Dynamic chat search filter
  const filteredChats = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return chats;
    return chats.filter(
      (chat) =>
        chat.title.toLowerCase().includes(term) ||
        (chat.subtitle && chat.subtitle.toLowerCase().includes(term)),
    );
  }, [chats, search]);

  // Dynamic document search filter
  const filteredDocs = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return docs;
    return docs.filter(
      (doc) =>
        doc.name.toLowerCase().includes(term) ||
        doc.typeLabel.toLowerCase().includes(term) ||
        doc.kind.toLowerCase().includes(term),
    );
  }, [docs, search]);

  // Dynamic user profile info
  const userName = isAuthenticated && user
    ? user.full_name.trim() || user.email.split("@")[0]
    : "Guest Explorer";

  const userSubtitle = isAuthenticated && user
    ? user.role === "admin"
      ? "System Administrator"
      : user.email
    : "Guest Session";

  const initials = useMemo(() => {
    if (isAuthenticated && user) {
      if (user.full_name?.trim()) {
        const parts = user.full_name.trim().split(/\s+/);
        if (parts.length >= 2 && parts[0] && parts[1]) {
          return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
        }
        return (parts[0] || "").slice(0, 2).toUpperCase();
      }
      return (user.email || "U").charAt(0).toUpperCase();
    }
    return "GE";
  }, [user, isAuthenticated]);

  return (
    <aside
      className={cn(
        "z-30 flex h-full shrink-0 flex-col overflow-hidden border-r border-[rgba(255,255,255,0.06)] bg-[rgba(6,10,22,0.82)] backdrop-blur-2xl transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] shadow-[4px_0_30px_rgba(0,0,0,0.5)]",
        open ? "w-[280px]" : "w-0 md:w-[72px]",
      )}
    >
      {/* Sidebar Header */}
      <div className="flex items-center gap-2 px-3.5 py-4 border-b border-white/5">
        <Link to="/" className="flex min-w-0 items-center gap-2.5">
          <SparkCore variant="compact" className="shrink-0" />
          {open && (
            <div className="min-w-0">
              <span className="block truncate text-sm font-bold tracking-tight text-white font-display">
                SS SPARK
              </span>
              <span className="block truncate text-[10px] font-mono text-sky-400/80 uppercase">
                AI Intelligence
              </span>
            </div>
          )}
        </Link>
        {open && (
          <button
            className="ml-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/5 text-slate-400 hover:border-sky-400/30 hover:bg-slate-800/60 hover:text-white transition-all cursor-pointer"
            onClick={onToggle}
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {!open && (
        <div className="hidden justify-center py-3 md:flex">
          <button
            className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/5 bg-slate-900/50 text-slate-400 hover:border-sky-400/30 hover:text-white transition-all cursor-pointer"
            onClick={onToggle}
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* New Chat Button */}
      <div className="px-3 pt-3">
        <button
          onClick={onNewChat}
          className={cn(
            "w-full flex items-center justify-center gap-2 rounded-xl border border-sky-400/30 bg-gradient-to-r from-sky-500/15 via-indigo-500/20 to-sky-500/15 py-2.5 px-3 text-xs font-semibold text-sky-100 shadow-[0_0_20px_rgba(56,189,248,0.1)] transition-all hover:border-sky-400/60 hover:bg-sky-500/25 active:scale-[0.98] cursor-pointer group",
            !open && "px-0",
          )}
        >
          <MessageSquarePlus className="h-4 w-4 text-sky-400 transition-transform group-hover:scale-110" />
          {open && <span>New Session</span>}
        </button>
      </div>

      {/* Search Input */}
      {open && (
        <div className="relative mt-3 px-3">
          <Search className="pointer-events-none absolute top-1/2 left-6 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <Input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search sessions & papers..."
            className="h-8.5 rounded-xl border-white/10 bg-slate-950/50 pl-8.5 text-xs text-slate-200 placeholder:text-slate-600 focus-visible:border-sky-400/50 focus-visible:ring-1 focus-visible:ring-sky-400/25"
          />
        </div>
      )}

      {/* Scrollable list */}
      <ScrollArea className="mt-3 flex-1 px-3">
        <div className="pb-4 space-y-4">
          {/* Recent Chats */}
          <div>
            <SectionLabel open={open} icon={History} label="Recent Sessions" />
            <div className="space-y-1">
              {filteredChats.map((chat) => (
                <button
                  key={chat.id}
                  onClick={() => onSelectChat(chat.id)}
                  title={chat.title}
                  className={cn(
                    "relative flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-xs transition-all duration-200 cursor-pointer",
                    activeChat === chat.id
                      ? "border border-sky-400/30 bg-sky-950/40 text-sky-100 font-medium shadow-[0_0_15px_rgba(56,189,248,0.12)]"
                      : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200",
                  )}
                >
                  {activeChat === chat.id && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-sky-400 shadow-[0_0_8px_#38bdf8]" />
                  )}
                  <MessageSquarePlus className="h-3.5 w-3.5 shrink-0 opacity-60 text-sky-400" />
                  {open && (
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{chat.title}</span>
                      {chat.subtitle && (
                        <span className="block truncate text-[10px] text-slate-500">
                          {chat.subtitle}
                        </span>
                      )}
                    </span>
                  )}
                </button>
              ))}
              {open && filteredChats.length === 0 && (
                <p className="px-2.5 py-2 text-[11px] text-slate-500">
                  {search ? "No matching sessions." : "No recent sessions."}
                </p>
              )}
            </div>
          </div>

          <Separator className="bg-white/5" />

          {/* Documents */}
          <div>
            <div className="flex items-center justify-between px-2.5 pb-2">
              <SectionLabel open={open} icon={FileText} label={`Sources (${filteredDocs.length})`} />
              {open && (
                <button
                  onClick={onUpload}
                  className="text-[10px] font-mono font-medium text-sky-400 hover:text-sky-300 transition-colors"
                >
                  + Upload
                </button>
              )}
            </div>
            <div className="space-y-1">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.id}
                  title={doc.name}
                  className="flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs text-slate-400 transition-colors hover:bg-slate-900/60 hover:text-slate-200"
                >
                  {doc.kind === "image" ? (
                    <ImageIcon className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
                  ) : (
                    <FileText className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                  )}
                  {open && (
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-slate-200">
                        {doc.name}
                      </span>
                      <span className="block truncate text-[10px] text-slate-500">
                        {doc.pages} page{doc.pages === 1 ? "" : "s"} · {formatTime(doc.uploadedAt)}
                      </span>
                    </span>
                  )}
                </div>
              ))}
              {open && filteredDocs.length === 0 && (
                <button
                  onClick={onUpload}
                  className="w-full rounded-xl border border-dashed border-white/10 p-3 text-center text-[11px] text-slate-500 hover:border-sky-400/40 hover:text-slate-300 transition-colors cursor-pointer"
                >
                  {search ? "No matching files." : "+ Upload paper or notes"}
                </button>
              )}
            </div>
          </div>
        </div>
      </ScrollArea>

      {/* Bottom Footer Section */}
      <div className="mt-auto space-y-1 border-t border-white/5 p-3">
        {user?.role === "admin" && (
          <Link
            to="/admin"
            className={cn(
              "flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-semibold text-sky-300 transition-colors hover:bg-sky-950/40 border border-sky-400/20",
              !open && "justify-center",
            )}
            title="Admin Dashboard"
          >
            <Shield className="h-3.5 w-3.5 shrink-0 text-sky-400" />
            {open && <span>Admin Console</span>}
          </Link>
        )}

        <button
          onClick={onOpenSettings}
          className={cn(
            "flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs text-slate-400 hover:bg-slate-900/60 hover:text-slate-200 transition-colors cursor-pointer",
            !open && "justify-center",
          )}
        >
          <Settings className="h-3.5 w-3.5 shrink-0" />
          {open && <span>Workspace Settings</span>}
        </button>

        {/* User profile dock */}
        <button
          onClick={onOpenSettings}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-all duration-200 hover:bg-slate-900/80 cursor-pointer border border-transparent hover:border-white/5",
            !open && "justify-center",
          )}
        >
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={userName}
              className="h-7 w-7 shrink-0 rounded-full border border-sky-400/30 object-cover"
            />
          ) : (
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-500/30 to-indigo-500/30 border border-sky-400/40 text-[11px] font-semibold text-sky-200 shadow-sm">
              {initials}
            </span>
          )}
          {open && (
            <span className="min-w-0">
              <span className="block truncate text-xs font-medium text-slate-200">{userName}</span>
              <span className="block truncate text-[10px] text-slate-500 font-mono">
                {userSubtitle}
              </span>
            </span>
          )}
        </button>
      </div>
    </aside>
  );
});

function SectionLabel({
  open,
  icon: Icon,
  label,
}: {
  open: boolean;
  icon: typeof FileText;
  label: string;
}) {
  if (!open) return <div className="my-2 h-px bg-white/5" />;
  return (
    <div className="flex items-center gap-1.5 px-2.5 pb-2 text-[10px] font-mono font-medium tracking-wider text-slate-500 uppercase">
      <Icon className="h-3 w-3" />
      {label}
    </div>
  );
}
