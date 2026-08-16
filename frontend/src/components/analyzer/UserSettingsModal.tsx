import { useState, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  User as UserIcon,
  LogOut,
  UserPlus,
  Key,
  MessageSquare,
  Star,
  Trash2,
  ExternalLink,
  Shield,
  Search,
  CheckCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { sessionsApi, apiFetch, type SessionResponse } from "@/lib/api";

interface UserSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessions: SessionResponse[];
  onSelectSession: (id: string) => void;
  onRefreshSessions: () => void;
}

export function UserSettingsModal({
  open,
  onOpenChange,
  sessions,
  onSelectSession,
  onRefreshSessions,
}: UserSettingsModalProps) {
  const { user, isGuest, isAuthenticated, logout, clearAuth } = useAuth();
  const navigate = useNavigate();

  // Saved Chats state
  const [chatSearch, setChatSearch] = useState("");

  // API Keys state
  const [openaiKey, setOpenaiKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [keysLoading, setKeysLoading] = useState(false);
  const [keysStatus, setKeysStatus] = useState({
    has_openai: false,
    has_gemini: false,
    has_anthropic: false,
  });

  // Load API keys status on modal open
  useEffect(() => {
    if (open && isAuthenticated) {
      apiFetch<{
        success: boolean;
        data: { has_openai: boolean; has_gemini: boolean; has_anthropic: boolean };
      }>("/api/users/settings")
        .then((res) => {
          setKeysStatus(res.data);
        })
        .catch(() => {});
    }
  }, [open, isAuthenticated]);

  // Handle API keys submit
  async function handleSaveKeys(e: React.FormEvent) {
    e.preventDefault();
    setKeysLoading(true);
    try {
      await apiFetch("/api/users/settings", {
        method: "POST",
        body: JSON.stringify({
          openai_api_key: openaiKey || undefined,
          gemini_api_key: geminiKey || undefined,
          anthropic_api_key: anthropicKey || undefined,
        }),
      });
      toast.success("API keys saved successfully!");
      setOpenaiKey("");
      setGeminiKey("");
      setAnthropicKey("");
      // Refresh status
      const res = await apiFetch<{
        success: boolean;
        data: { has_openai: boolean; has_gemini: boolean; has_anthropic: boolean };
      }>("/api/users/settings");
      setKeysStatus(res.data);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to save API keys");
    } finally {
      setKeysLoading(false);
    }
  }

  // Handle Logout
  async function handleLogout() {
    onOpenChange(false);
    await logout();
    toast.success("Logged out successfully.");
    navigate({ to: "/login" });
  }

  // Handle Add Another Account
  function handleAddAccount() {
    onOpenChange(false);
    clearAuth();
    toast.info("Sign in with another account.");
    navigate({ to: "/login" });
  }

  // Handle Pin Session
  async function handleTogglePin(session: SessionResponse) {
    try {
      await sessionsApi.update(session.id, { pinned: !session.pinned });
      toast.success(session.pinned ? "Unpinned chat" : "Pinned chat to top");
      onRefreshSessions();
    } catch {
      toast.error("Failed to update chat");
    }
  }

  // Handle Delete Session
  async function handleDeleteSession(sessionId: string) {
    try {
      await sessionsApi.delete(sessionId);
      toast.success("Chat session deleted");
      onRefreshSessions();
    } catch {
      toast.error("Failed to delete chat");
    }
  }

  // Filtered chats
  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(chatSearch.trim().toLowerCase()),
  );

  const pinnedSessions = filteredSessions.filter((s) => s.pinned);
  const otherSessions = filteredSessions.filter((s) => !s.pinned);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl overflow-hidden p-0 sm:rounded-2xl">
        <DialogHeader className="border-b px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <UserIcon className="h-5 w-5 text-primary" />
            Account & Settings
          </DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="account" className="w-full">
          <div className="border-b px-6">
            <TabsList className="h-11 w-full justify-start gap-4 bg-transparent p-0">
              <TabsTrigger
                value="account"
                className="gap-2 rounded-none border-b-2 border-transparent px-2 pb-3 pt-2 text-sm font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground"
              >
                <Shield className="h-4 w-4" />
                Account
              </TabsTrigger>
              <TabsTrigger
                value="chats"
                className="gap-2 rounded-none border-b-2 border-transparent px-2 pb-3 pt-2 text-sm font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground"
              >
                <MessageSquare className="h-4 w-4" />
                Saved Chats ({sessions.length})
              </TabsTrigger>
              <TabsTrigger
                value="keys"
                className="gap-2 rounded-none border-b-2 border-transparent px-2 pb-3 pt-2 text-sm font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground"
              >
                <Key className="h-4 w-4" />
                API Keys
              </TabsTrigger>
            </TabsList>
          </div>

          {/* TAB 1: ACCOUNT & SECURITY */}
          <TabsContent value="account" className="space-y-6 p-6">
            {/* User Profile Card */}
            <div className="flex items-center justify-between rounded-xl border bg-muted/40 p-4">
              <div className="flex items-center gap-3.5">
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.full_name}
                    className="h-12 w-12 rounded-full border object-cover"
                  />
                ) : (
                  <div className="grid h-12 w-12 place-items-center rounded-full gradient-brand text-sm font-semibold text-brand-foreground">
                    {user?.full_name?.trim()
                      ? user.full_name
                          .trim()
                          .split(/\s+/)
                          .map((n) => n.charAt(0))
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()
                      : (user?.email || "GU").charAt(0).toUpperCase()}
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-foreground">
                      {user?.full_name || user?.email || "Guest User"}
                    </h3>
                    <Badge variant="outline" className="capitalize text-xs">
                      {user?.role || (isGuest ? "Guest" : "User")}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {user?.email || "Browsing in temporary guest mode"}
                  </p>
                </div>
              </div>

              {user?.provider && (
                <Badge variant="secondary" className="capitalize text-xs">
                  {user.provider} Auth
                </Badge>
              )}
            </div>

            {/* Account Actions */}
            <div className="space-y-3 pt-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Session Actions
              </h4>

              <div className="grid gap-3 sm:grid-cols-2">
                <Button
                  variant="outline"
                  onClick={handleAddAccount}
                  className="h-11 justify-start gap-2.5 rounded-xl border-dashed"
                >
                  <UserPlus className="h-4 w-4 text-primary" />
                  <span>Add another account</span>
                </Button>

                <Button
                  variant="destructive"
                  onClick={handleLogout}
                  className="h-11 justify-start gap-2.5 rounded-xl"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Log out of SS Spark</span>
                </Button>
              </div>
            </div>
          </TabsContent>

          {/* TAB 2: SAVED CHATS */}
          <TabsContent value="chats" className="space-y-4 p-6">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={chatSearch}
                onChange={(e) => setChatSearch(e.target.value)}
                placeholder="Search saved chats..."
                className="pl-9 text-sm"
              />
            </div>

            <div className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
              {pinnedSessions.length > 0 && (
                <div>
                  <p className="mb-1 text-[11px] font-semibold text-muted-foreground uppercase">
                    Pinned
                  </p>
                  <div className="space-y-1.5">
                    {pinnedSessions.map((session) => (
                      <ChatItemRow
                        key={session.id}
                        session={session}
                        onSelect={() => {
                          onSelectSession(session.id);
                          onOpenChange(false);
                        }}
                        onTogglePin={() => handleTogglePin(session)}
                        onDelete={() => handleDeleteSession(session.id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              <div>
                {pinnedSessions.length > 0 && (
                  <p className="mt-3 mb-1 text-[11px] font-semibold text-muted-foreground uppercase">
                    All Chats
                  </p>
                )}
                <div className="space-y-1.5">
                  {otherSessions.map((session) => (
                    <ChatItemRow
                      key={session.id}
                      session={session}
                      onSelect={() => {
                        onSelectSession(session.id);
                        onOpenChange(false);
                      }}
                      onTogglePin={() => handleTogglePin(session)}
                      onDelete={() => handleDeleteSession(session.id)}
                    />
                  ))}
                </div>
              </div>

              {filteredSessions.length === 0 && (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {chatSearch ? "No matching chats found." : "No saved chats yet."}
                </div>
              )}
            </div>
          </TabsContent>

          {/* TAB 3: API KEYS */}
          <TabsContent value="keys" className="p-6">
            <form onSubmit={handleSaveKeys} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">OpenAI API Key</label>
                <div className="relative">
                  <Input
                    type="password"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    placeholder={
                      keysStatus.has_openai ? "•••••••••••••••• (Configured)" : "sk-..."
                    }
                    className="text-sm"
                  />
                  {keysStatus.has_openai && (
                    <CheckCircle className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-emerald-500" />
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Google Gemini API Key
                </label>
                <div className="relative">
                  <Input
                    type="password"
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    placeholder={
                      keysStatus.has_gemini ? "•••••••••••••••• (Configured)" : "AIzaSy..."
                    }
                    className="text-sm"
                  />
                  {keysStatus.has_gemini && (
                    <CheckCircle className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-emerald-500" />
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-foreground">
                  Anthropic Claude API Key
                </label>
                <div className="relative">
                  <Input
                    type="password"
                    value={anthropicKey}
                    onChange={(e) => setAnthropicKey(e.target.value)}
                    placeholder={
                      keysStatus.has_anthropic ? "•••••••••••••••• (Configured)" : "sk-ant-..."
                    }
                    className="text-sm"
                  />
                  {keysStatus.has_anthropic && (
                    <CheckCircle className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-emerald-500" />
                  )}
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <Button type="submit" disabled={keysLoading} className="gradient-brand">
                  {keysLoading ? "Saving..." : "Save API Keys"}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

function ChatItemRow({
  session,
  onSelect,
  onTogglePin,
  onDelete,
}: {
  session: SessionResponse;
  onSelect: () => void;
  onTogglePin: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group flex items-center justify-between rounded-xl border bg-card px-3 py-2.5 transition-colors hover:bg-accent/50">
      <button
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
      >
        <MessageSquare className="h-4 w-4 shrink-0 text-primary opacity-70" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{session.title}</p>
          <p className="truncate text-[11px] text-muted-foreground">
            {session.message_count || 0} messages · {new Date(session.updated_at).toLocaleDateString()}
          </p>
        </div>
      </button>

      <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onTogglePin}
          title={session.pinned ? "Unpin" : "Pin to top"}
        >
          <Star
            className={`h-4 w-4 ${session.pinned ? "fill-amber-400 text-amber-400" : "text-muted-foreground"}`}
          />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onSelect}
          title="Open chat"
        >
          <ExternalLink className="h-4 w-4 text-muted-foreground" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:bg-destructive/10"
          onClick={onDelete}
          title="Delete chat"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
