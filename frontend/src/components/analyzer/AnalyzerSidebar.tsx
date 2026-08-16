import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import {
  BrainCircuit,
  ChevronLeft,
  FileText,
  ImageIcon,
  MessageSquarePlus,
  PanelLeftOpen,
  Search,
  Settings,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { formatTime, type UploadedDoc } from "@/lib/analyzer";
import { useAuth } from "@/lib/auth";

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

export function AnalyzerSidebar({
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

  // Dynamic user profile info
  const userName = isAuthenticated && user
    ? user.full_name.trim() || user.email.split("@")[0]
    : isGuest
    ? "Guest User"
    : "Guest User";

  const userSubtitle = isAuthenticated && user
    ? user.role === "admin"
      ? "Admin"
      : user.email
    : "Guest mode";

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
    return "GU";
  }, [user, isAuthenticated]);

  return (
    <aside
      className={cn(
        "z-30 flex h-full shrink-0 flex-col overflow-hidden border-r bg-sidebar/80 backdrop-blur-xl transition-[width] duration-300 ease-out",
        open ? "w-[280px]" : "w-0 md:w-[76px]",
      )}
    >
      <div className="flex items-center gap-2 px-3 py-4">
        <Link to="/" className="flex min-w-0 items-center gap-2.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl gradient-brand text-brand-foreground shadow-lg">
            <BrainCircuit className="h-5 w-5" />
          </span>
          {open && (
            <span className="min-w-0">
              <span className="block truncate text-sm font-bold tracking-tight">SS SPARK</span>
              <span className="block truncate text-[11px] text-muted-foreground">
                AI Question Paper Analyzer
              </span>
            </span>
          )}
        </Link>
        {open && (
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto shrink-0"
            onClick={onToggle}
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        )}
      </div>

      {!open && (
        <div className="hidden justify-center px-3 md:flex">
          <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Expand sidebar">
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
        </div>
      )}

      <div className="px-3">
        <Button
          onClick={onNewChat}
          className={cn("w-full gradient-brand text-brand-foreground hover-lift", !open && "px-0")}
        >
          <MessageSquarePlus className="h-4 w-4" />
          {open && <span>New chat</span>}
        </Button>
      </div>

      {open && (
        <div className="relative mt-3 px-3">
          <Search className="pointer-events-none absolute top-1/2 left-6 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search chats"
            className="h-9 bg-background/50 pl-9 text-sm"
          />
        </div>
      )}

      <ScrollArea className="mt-3 flex-1 px-3">
        <div className="pb-4">
          <SectionLabel open={open} icon={History} label="Recent chats" />
          <div className="space-y-1">
            {filteredChats.map((chat) => (
              <button
                key={chat.id}
                onClick={() => onSelectChat(chat.id)}
                title={chat.title}
                className={cn(
                  "flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left text-sm transition-colors",
                  activeChat === chat.id
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                )}
              >
                <MessageSquarePlus className="h-4 w-4 shrink-0 opacity-70" />
                {open && (
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{chat.title}</span>
                    {chat.subtitle && (
                      <span className="block truncate text-[11px] opacity-70">{chat.subtitle}</span>
                    )}
                  </span>
                )}
              </button>
            ))}
            {open && filteredChats.length === 0 && (
              <p className="px-2.5 py-3 text-xs text-muted-foreground">
                {search ? "No matching chats found." : "No recent chats yet."}
              </p>
            )}
          </div>

          <Separator className="my-4" />

          <SectionLabel open={open} icon={FileText} label="Uploaded documents" />
          <div className="space-y-1">
            {docs.slice(0, 6).map((doc) => (
              <div
                key={doc.id}
                title={doc.name}
                className="flex items-center gap-2 rounded-xl px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent/60"
              >
                {doc.kind === "image" ? (
                  <ImageIcon className="h-4 w-4 shrink-0 text-chart-2" />
                ) : (
                  <FileText className="h-4 w-4 shrink-0 text-chart-1" />
                )}
                {open && (
                  <span className="min-w-0">
                    <span className="block truncate text-foreground/90">{doc.name}</span>
                    <span className="block truncate text-[11px]">
                      {doc.pages} pages · {formatTime(doc.uploadedAt)}
                    </span>
                  </span>
                )}
              </div>
            ))}
            {open && docs.length === 0 && (
              <button
                onClick={onUpload}
                className="w-full rounded-xl border border-dashed px-2.5 py-3 text-xs text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground"
              >
                No documents yet — upload to begin
              </button>
            )}
          </div>
        </div>
      </ScrollArea>

      <div className="mt-auto space-y-1 border-t p-3">
        <button
          onClick={onOpenSettings}
          className={cn(
            "flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-foreground cursor-pointer",
            !open && "justify-center",
          )}
        >
          <Settings className="h-4 w-4 shrink-0" />
          {open && <span>Settings</span>}
        </button>

        <button
          onClick={onOpenSettings}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-sidebar-accent/60 cursor-pointer",
            !open && "justify-center",
          )}
        >
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt={userName}
              className="h-8 w-8 shrink-0 rounded-full border object-cover"
            />
          ) : (
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full gradient-brand text-xs font-semibold text-brand-foreground">
              {initials}
            </span>
          )}
          {open && (
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{userName}</span>
              <span className="block truncate text-[11px] text-muted-foreground">
                {userSubtitle}
              </span>
            </span>
          )}
        </button>
      </div>
    </aside>
  );
}

function SectionLabel({
  open,
  icon: Icon,
  label,
}: {
  open: boolean;
  icon: typeof FileText;
  label: string;
}) {
  if (!open) return <div className="my-2 h-px bg-sidebar-border" />;
  return (
    <div className="flex items-center gap-1.5 px-2.5 pb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
      <Icon className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}
