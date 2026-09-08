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
  Sparkles,
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
      <DialogContent className="max-w-2xl overflow-hidden p-0 sm:rounded-3xl border-border/70 bg-card/95 backdrop-blur-2xl shadow-2xl">
        <DialogHeader className="border-b border-border/50 px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center gap-2.5 text-xl font-bold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-xl gradient-brand text-brand-foreground shadow-xs">
              <UserIcon className="h-4.5 w-4.5" />
            </span>
            <span>Account & Settings</span>
          </DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="account" className="w-full">
          <div className="border-b border-border/50 px-6">
            <TabsList className="h-12 w-full justify-start gap-4 bg-transparent p-0">
              <TabsTrigger
                value="account"
                className="gap-2 rounded-none border-b-2 border-transparent px-3 pb-3.5 pt-2 text-sm font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground transition-all"
              >
                <Shield className="h-4 w-4 text-primary" />
                Account
              </TabsTrigger>
              <TabsTrigger
                value="chats"
                className="gap-2 rounded-none border-b-2 border-transparent px-3 pb-3.5 pt-2 text-sm font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground transition-all"
              >
                <MessageSquare className="h-4 w-4" />
                Saved Chats ({sessions.length})
              </TabsTrigger>
              <TabsTrigger
                value="keys"
                className="gap-2 rounded-none border-b-2 border-transparent px-3 pb-3.5 pt-2 text-sm font-medium data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground transition-all"
              >
                <Key className="h-4 w-4" />
                API Keys
              </TabsTrigger>
            </TabsList>
          </div>

          {/* TAB 1: ACCOUNT & SECURITY */}
          <TabsContent value="account" className="space-y-6 p-6">
            {/* User Profile Card */}
            <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-muted/30 p-4.5 backdrop-blur-sm">
              <div className="flex items-center gap-3.5">
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.full_name}
                    className="h-12 w-12 rounded-full border border-border/60 object-cover shadow-xs"
                  />
                ) : (
                  <div className="grid h-12 w-12 place-items-center rounded-full gradient-brand text-sm font-bold text-brand-foreground shadow-sm">
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
                    <Badge variant="outline" className="capitalize text-[11px] px-2 py-0.5">
                      {user?.role || (isGuest ? "Guest" : "User")}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {user?.email || "Browsing in temporary guest mode"}
                  </p>
                </div>
              </div>

              {user?.provider && (
                <Badge variant="secondary" className="capitalize text-xs px-2.5 py-1">
                  {user.provider} Auth
                </Badge>
              )}
            </div>

            {/* Account Actions */}
            <div className="space-y-3 pt-1">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground/80">
                Session Actions
              </h4>

              <div className="grid gap-3 sm:grid-cols-2">
                {user?.role === "admin" && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      onOpenChange(false);
                      navigate({ to: "/admin" });
                    }}
                    className="h-11 justify-start gap-2.5 rounded-xl border-primary/40 bg-primary/5 text-primary hover:bg-primary/10 sm:col-span-2 cursor-pointer"
                  >
                    <Shield className="h-4 w-4" />
                    <span className="font-semibold">Open Admin Control Panel</span>
                  </Button>
                )}

                <Button
                  variant="outline"
                  onClick={handleAddAccount}
                  className="h-11 justify-start gap-2.5 rounded-xl border-border/80 hover:bg-accent cursor-pointer"
                >
                  <UserPlus className="h-4 w-4 text-primary" />
                  <span>Add another account</span>
                </Button>

                <Button
                  variant="destructive"
                  onClick={handleLogout}
                  className="h-11 justify-start gap-2.5 rounded-xl cursor-pointer"
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
              <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
              <Input
                value={chatSearch}
                onChange={(e) => setChatSearch(e.target.value)}
                placeholder="Search saved chats..."
                className="pl-10 h-10 text-sm bg-background/50 border-border/70 rounded-xl"
              />
            </div>

            <div className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
              {pinnedSessions.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[11px] font-bold text-muted-foreground/80 uppercase tracking-wider">
                    Pinned Chats
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
                  <p className="mt-3.5 mb-1.5 text-[11px] font-bold text-muted-foreground/80 uppercase tracking-wider">
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
                <div className="py-10 text-center text-sm text-muted-foreground">
                  {chatSearch ? "No matching chats found." : "No saved chats yet."}
                </div>
              )}
            </div>
          </TabsContent>

          {/* TAB 3: API KEYS */}
          <TabsContent value="keys" className="p-6">
            <form onSubmit={handleSaveKeys} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">OpenAI API Key</label>
                <div className="relative">
                  <Input
                    type="password"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    placeholder={
                      keysStatus.has_openai ? "•••••••••••••••• (Configured)" : "sk-..."
                    }
                    className="text-sm rounded-xl h-10 pr-10"
                  />
                  {keysStatus.has_openai && (
                    <CheckCircle className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-emerald-500" />
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
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
                    className="text-sm rounded-xl h-10 pr-10"
                  />
                  {keysStatus.has_gemini && (
                    <CheckCircle className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-emerald-500" />
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
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
                    className="text-sm rounded-xl h-10 pr-10"
                  />
                  {keysStatus.has_anthropic && (
                    <CheckCircle className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-emerald-500" />
                  )}
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <Button type="submit" disabled={keysLoading} className="gradient-brand text-brand-foreground shadow-md shadow-primary/20 hover-lift cursor-pointer">
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
    <div className="group flex items-center justify-between rounded-xl border border-border/50 bg-card/60 px-3.5 py-2.5 transition-all hover:bg-accent/60 hover:border-border/80">
      <button
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2.5 text-left cursor-pointer"
      >
        <MessageSquare className="h-4 w-4 shrink-0 text-primary opacity-70 group-hover:opacity-100 transition-opacity" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground group-hover:text-primary transition-colors">{session.title}</p>
          <p className="truncate text-[11px] text-muted-foreground">
            {session.message_count || 0} messages · {new Date(session.updated_at).toLocaleDateString()}
          </p>
        </div>
      </button>

      <div className="flex items-center gap-1 opacity-70 group-hover:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 rounded-lg"
          onClick={onTogglePin}
          title={session.pinned ? "Unpin" : "Pin to top"}
        >
          <Star
            className={`h-3.5 w-3.5 ${session.pinned ? "fill-amber-400 text-amber-400" : "text-muted-foreground"}`}
          />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 rounded-lg"
          onClick={onSelect}
          title="Open chat"
        >
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          onClick={onDelete}
          title="Delete chat"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
