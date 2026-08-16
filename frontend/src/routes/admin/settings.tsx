import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { adminApi, type SystemSettings } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/settings")({
  head: () => ({ meta: [{ title: "System Settings | SS Spark Admin" }] }),
  component: AdminSettingsPage,
});

function AdminSettingsPage() {
  const [settings, setSettings] = useState<Partial<SystemSettings>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminApi.getSettings().then((res) => {
      setSettings(res.data);
      setLoading(false);
    }).catch(() => {
      toast.error("Failed to load settings");
      setLoading(false);
    });
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminApi.updateSettings(settings);
      toast.success("Settings saved!");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const set = (key: string, value: unknown) => setSettings((p) => ({ ...p, [key]: value }));

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 rounded-lg bg-muted" />
          <div className="h-64 rounded-2xl bg-muted" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>System Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Configure platform-wide AI and file settings</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6 max-w-2xl">
        {/* AI Models */}
        <div className="rounded-2xl border border-border p-5 space-y-4" style={{ background: "var(--card)" }}>
          <h2 className="text-sm font-semibold" style={{ fontFamily: "var(--font-display)" }}>AI Configuration</h2>

          {[
            { key: "llm_model", label: "LLM Model", placeholder: "gpt-4o-mini" },
            { key: "embedding_model", label: "Embedding Model", placeholder: "text-embedding-3-small" },
            { key: "ocr_engine", label: "OCR Engine", placeholder: "tesseract" },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-sm font-medium mb-2">{label}</label>
              <input
                value={(settings as Record<string, unknown>)[key] as string ?? ""}
                onChange={(e) => set(key, e.target.value)}
                placeholder={placeholder}
                className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          ))}

          {[
            { key: "chunk_size", label: "Chunk Size (tokens)", min: 100, max: 2000 },
            { key: "chunk_overlap", label: "Chunk Overlap (tokens)", min: 0, max: 500 },
          ].map(({ key, label, min, max }) => (
            <div key={key}>
              <label className="block text-sm font-medium mb-2">{label}</label>
              <input
                type="number"
                value={(settings as Record<string, unknown>)[key] as number ?? 0}
                onChange={(e) => set(key, Number(e.target.value))}
                min={min}
                max={max}
                className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          ))}
        </div>

        {/* File settings */}
        <div className="rounded-2xl border border-border p-5 space-y-4" style={{ background: "var(--card)" }}>
          <h2 className="text-sm font-semibold" style={{ fontFamily: "var(--font-display)" }}>File Upload Settings</h2>

          <div>
            <label className="block text-sm font-medium mb-2">Max Upload Size (MB)</label>
            <input
              type="number"
              value={settings.max_upload_size_mb ?? 50}
              onChange={(e) => set("max_upload_size_mb", Number(e.target.value))}
              min={1}
              max={500}
              className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Rate Limit (requests/minute)</label>
            <input
              type="number"
              value={settings.rate_limit_requests_per_minute ?? 60}
              onChange={(e) => set("rate_limit_requests_per_minute", Number(e.target.value))}
              min={1}
              max={1000}
              className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>

        {/* Maintenance */}
        <div className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
          <h2 className="text-sm font-semibold mb-4" style={{ fontFamily: "var(--font-display)" }}>Maintenance</h2>
          <label className="flex items-center justify-between cursor-pointer">
            <div>
              <p className="text-sm font-medium">Maintenance Mode</p>
              <p className="text-xs text-muted-foreground mt-0.5">Prevent non-admin users from accessing the platform</p>
            </div>
            <div
              onClick={() => set("maintenance_mode", !settings.maintenance_mode)}
              className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer"
              style={{
                background: settings.maintenance_mode ? "var(--primary)" : "var(--border)",
              }}
            >
              <span
                className="inline-block h-4 w-4 rounded-full bg-white shadow transition-transform"
                style={{ transform: settings.maintenance_mode ? "translateX(22px)" : "translateX(2px)" }}
              />
            </div>
          </label>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift"
        >
          {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <><Save className="h-4 w-4" /> Save Settings</>}
        </button>
      </form>
    </div>
  );
}
