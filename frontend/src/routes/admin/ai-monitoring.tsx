import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Activity, AlertCircle, CheckCircle2, Clock, FileText, MessageSquare, RefreshCw, Zap,
} from "lucide-react";
import { adminApi } from "@/lib/admin-api";
import type { SystemHealth } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/ai-monitoring")({
  head: () => ({ meta: [{ title: "AI Monitoring | SS Spark Admin" }] }),
  component: AdminAIMonitoringPage,
});

function AdminAIMonitoringPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getSystemHealth();
      setHealth(res.data);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const getStatusIcon = (status: string) => {
    if (status === "ok") return <CheckCircle2 className="h-5 w-5 text-emerald-400" />;
    if (status === "error") return <AlertCircle className="h-5 w-5 text-destructive" />;
    return <Clock className="h-5 w-5 text-yellow-400 animate-spin" />;
  };

  const services = health
    ? [
        {
          name: "MongoDB",
          icon: <Activity className="h-5 w-5" />,
          status: health.mongodb.status,
          details: [
            { label: "Database", value: health.mongodb.database ?? "N/A" },
            { label: "Status", value: health.mongodb.error ?? "Connected" },
          ],
        },
        {
          name: "ChromaDB Vector Store",
          icon: <FileText className="h-5 w-5" />,
          status: health.chromadb.status,
          details: [
            { label: "Indexed Chunks", value: String(health.chromadb.chunk_count ?? 0) },
            { label: "Status", value: health.chromadb.error ?? "OK" },
          ],
        },
        {
          name: "PaperQA Engine",
          icon: <MessageSquare className="h-5 w-5" />,
          status: health.paperqa.status,
          details: [
            { label: "Indexed Documents", value: String(health.paperqa.indexed_documents) },
            { label: "Mode", value: "RAG (BM25 + Vector)" },
          ],
        },
        {
          name: "API Server",
          icon: <Zap className="h-5 w-5" />,
          status: "ok",
          details: [
            { label: "Python", value: health.server.python.split(" ")[0] ?? "N/A" },
            { label: "Platform", value: health.server.platform },
          ],
        },
      ]
    : [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>AI Monitoring</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time status of AI services and vector store
            {lastRefreshed && ` · Last refreshed ${lastRefreshed.toLocaleTimeString()}`}
          </p>
        </div>
        <button onClick={load}
                className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm hover:bg-accent transition-colors">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-40 rounded-2xl bg-muted animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {services.map(({ name, icon, status, details }) => (
            <div key={name} className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl"
                       style={{ background: "color-mix(in oklab, var(--primary) 18%, transparent)", color: "var(--primary)" }}>
                    {icon}
                  </div>
                  <div>
                    <p className="font-semibold">{name}</p>
                    <p className="text-xs text-muted-foreground capitalize">{status}</p>
                  </div>
                </div>
                {getStatusIcon(status)}
              </div>
              <div className="space-y-2 border-t border-border pt-3">
                {details.map(({ label, value }) => (
                  <div key={label} className="flex justify-between text-sm">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-medium font-mono text-xs">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tips */}
      <div className="rounded-2xl border border-border p-5" style={{ background: "var(--card)" }}>
        <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: "var(--font-display)" }}>About the AI Stack</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-sm text-muted-foreground">
          <div>
            <p className="font-medium text-foreground mb-1">PaperQA</p>
            <p>Scientific paper Q&A with automatic citation extraction and fact-checking.</p>
          </div>
          <div>
            <p className="font-medium text-foreground mb-1">Hybrid Search</p>
            <p>Combines BM25 keyword search + vector similarity for higher accuracy retrieval.</p>
          </div>
          <div>
            <p className="font-medium text-foreground mb-1">ChromaDB</p>
            <p>Local vector store for semantic embeddings — no cloud dependency required.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
