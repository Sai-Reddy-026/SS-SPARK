import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Bell, Loader2, Send } from "lucide-react";
import { toast } from "sonner";
import { adminApi } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/notifications")({
  head: () => ({ meta: [{ title: "Notifications | SS Spark Admin" }] }),
  component: AdminNotificationsPage,
});

function AdminNotificationsPage() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState("info");
  const [userId, setUserId] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) {
      toast.error("Title and body are required");
      return;
    }
    setLoading(true);
    try {
      await adminApi.sendNotification({
        title: title.trim(),
        body: body.trim(),
        kind,
        user_id: userId.trim() || undefined,
      });
      toast.success("Notification sent!");
      setTitle("");
      setBody("");
      setUserId("");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setLoading(false);
    }
  };

  const kindStyles: Record<string, { bg: string; color: string }> = {
    info: { bg: "color-mix(in oklab, var(--primary) 18%, transparent)", color: "var(--primary)" },
    success: { bg: "oklch(0.72 0.16 158 / 15%)", color: "oklch(0.72 0.16 158)" },
    warning: { bg: "oklch(0.79 0.16 78 / 15%)", color: "oklch(0.79 0.16 78)" },
    error: { bg: "oklch(0.62 0.21 22 / 15%)", color: "oklch(0.62 0.21 22)" },
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Notifications</h1>
        <p className="text-sm text-muted-foreground mt-1">Send platform announcements and alerts</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="rounded-2xl border border-border p-6" style={{ background: "var(--card)" }}>
          <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
            Send Notification
          </h2>
          <form onSubmit={handleSend} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Announcement title…"
                className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Message</label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={4}
                placeholder="Your message…"
                className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Type</label>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(kindStyles).map(([k, { bg, color }]) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setKind(k)}
                    className="rounded-full px-3 py-1 text-xs font-medium transition-all"
                    style={{
                      background: kind === k ? bg : "transparent",
                      color: kind === k ? color : "var(--muted-foreground)",
                      border: `1px solid ${kind === k ? color : "var(--border)"}`,
                    }}
                  >
                    {k.charAt(0).toUpperCase() + k.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                Target User ID <span className="text-muted-foreground font-normal">(leave blank for broadcast)</span>
              </label>
              <input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="Optional user ID…"
                className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift"
            >
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending…</> : <><Send className="h-4 w-4" /> Send Notification</>}
            </button>
          </form>
        </div>

        {/* Preview */}
        <div className="rounded-2xl border border-border p-6" style={{ background: "var(--card)" }}>
          <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>
            Preview
          </h2>
          <div className="rounded-xl border p-4 transition-all"
               style={{
                 background: kindStyles[kind]?.bg ?? kindStyles.info.bg,
                 borderColor: kindStyles[kind]?.color ?? kindStyles.info.color,
               }}>
            <div className="flex items-start gap-3">
              <Bell className="h-5 w-5 flex-shrink-0 mt-0.5"
                    style={{ color: kindStyles[kind]?.color ?? kindStyles.info.color }} />
              <div>
                <p className="font-semibold text-sm" style={{ color: kindStyles[kind]?.color ?? kindStyles.info.color }}>
                  {title || "Notification title"}
                </p>
                <p className="text-sm text-foreground/80 mt-1 whitespace-pre-wrap">
                  {body || "Your notification message will appear here."}
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  {userId ? `→ User: ${userId}` : "→ Broadcast to all users"}
                </p>
              </div>
            </div>
          </div>

          {/* Tips */}
          <div className="mt-6 space-y-2">
            <p className="text-sm font-medium">Tips:</p>
            <ul className="text-xs text-muted-foreground space-y-1.5">
              <li>• Leave User ID blank to send to all users (broadcast)</li>
              <li>• Use <strong>info</strong> for general announcements</li>
              <li>• Use <strong>warning</strong> for maintenance notices</li>
              <li>• Use <strong>success</strong> for feature launches</li>
              <li>• Use <strong>error</strong> for urgent alerts</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
