import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { adminApi, type AdminDocument } from "@/lib/admin-api";

export const Route = createFileRoute("/admin/documents")({
  head: () => ({ meta: [{ title: "Document Management | SS Spark Admin" }] }),
  component: AdminDocumentsPage,
});

function AdminDocumentsPage() {
  const [docs, setDocs] = useState<AdminDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 50;

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getDocuments({ skip: page * limit, limit, search: search || undefined });
      setDocs(res.data);
      setTotal(res.total);
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page]);

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This removes it from the index permanently.`)) return;
    try {
      await adminApi.deleteDocument(id);
      toast.success(`"${name}" deleted`);
      load();
    } catch { toast.error("Failed to delete document"); }
  };

  const handleReindex = async (id: string, name: string) => {
    try {
      await adminApi.reindexDocument(id);
      toast.success(`"${name}" re-indexed`);
    } catch { toast.error("Failed to re-index"); }
  };

  const kindColor: Record<string, string> = {
    pdf: "oklch(0.62 0.21 22)", docx: "oklch(0.68 0.22 45)",
    pptx: "oklch(0.79 0.16 78)", txt: "oklch(0.72 0.16 158)", image: "oklch(0.76 0.19 60)",
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Documents</h1>
          <p className="text-sm text-muted-foreground mt-1">{total} total across all users</p>
        </div>
        <button onClick={load}
                className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-sm hover:bg-accent transition-colors">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); setPage(0); load(); }} className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search documents by name…"
          className="w-full rounded-xl border bg-card pl-9 pr-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary"
        />
      </form>

      <div className="rounded-2xl border border-border overflow-hidden" style={{ background: "var(--card)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Name</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Type</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Size</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Pages</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Chunks</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Uploaded</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 rounded bg-muted animate-pulse" style={{ width: j === 0 ? "200px" : "60px" }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : docs.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-12 text-muted-foreground">No documents found.</td></tr>
              ) : (
                docs.map((doc) => (
                  <tr key={doc.id} className="border-b border-border hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-3 font-medium max-w-xs truncate">{doc.name}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full px-2 py-0.5 text-xs font-medium"
                            style={{
                              background: `${kindColor[doc.kind] ?? "oklch(0.71 0.028 274)"} / 15%`,
                              color: kindColor[doc.kind] ?? "oklch(0.71 0.028 274)",
                            }}>
                        {doc.kind}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{doc.size_mb.toFixed(2)} MB</td>
                    <td className="px-4 py-3 text-muted-foreground">{doc.pages}</td>
                    <td className="px-4 py-3 text-muted-foreground">{doc.chunk_count}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => handleReindex(doc.id, doc.name)} title="Re-index"
                                className="p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-primary">
                          <RefreshCw className="h-4 w-4" />
                        </button>
                        <button onClick={() => handleDelete(doc.id, doc.name)} title="Delete"
                                className="p-1.5 rounded-lg hover:bg-destructive/10 transition-colors text-muted-foreground hover:text-destructive">
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
