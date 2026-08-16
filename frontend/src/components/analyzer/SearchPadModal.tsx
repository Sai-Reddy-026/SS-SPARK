import { useState, useMemo } from "react";
import {
  FileText,
  Search,
  FileImage,
  FileType2,
  Trash2,
  CloudUpload,
  Sparkles,
  Layers,
  Clock,
  ExternalLink,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { UploadDropzone } from "@/components/analyzer/UploadDropzone";
import { formatTime, type UploadedDoc } from "@/lib/analyzer";

const iconMap = {
  pdf: FileText,
  docx: FileType2,
  txt: FileType2,
  image: FileImage,
};

interface SearchPadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  docs: UploadedDoc[];
  onUploadFiles: (files: File[]) => void;
  onDeleteDoc: (docId: string) => void;
  onAskAboutDoc?: (docName: string) => void;
}

export function SearchPadModal({
  open,
  onOpenChange,
  docs,
  onUploadFiles,
  onDeleteDoc,
  onAskAboutDoc,
}: SearchPadModalProps) {
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");

  const filteredDocs = useMemo(() => {
    let result = docs;
    if (activeTab === "pdf") {
      result = result.filter((d) => d.kind === "pdf" || d.kind === "docx" || d.kind === "txt");
    } else if (activeTab === "images") {
      result = result.filter((d) => d.kind === "image");
    }

    const q = query.trim().toLowerCase();
    if (!q) return result;
    return result.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.typeLabel.toLowerCase().includes(q) ||
        d.kind.toLowerCase().includes(q),
    );
  }, [docs, query, activeTab]);

  const pdfCount = useMemo(
    () => docs.filter((d) => d.kind !== "image").length,
    [docs],
  );
  const imageCount = useMemo(
    () => docs.filter((d) => d.kind === "image").length,
    [docs],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl overflow-hidden p-0 sm:rounded-2xl">
        <DialogHeader className="border-b px-6 pt-6 pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-xl font-bold">
              <span className="grid h-8 w-8 place-items-center rounded-xl gradient-brand text-brand-foreground shadow-md">
                <Search className="h-4 w-4" />
              </span>
              Search Pad & Document Workspace
            </DialogTitle>
            <Badge variant="outline" className="gap-1 text-xs">
              <Sparkles className="h-3 w-3 text-chart-2" />
              {docs.length} Document{docs.length === 1 ? "" : "s"}
            </Badge>
          </div>
        </DialogHeader>

        <div className="px-6 pt-4">
          {/* Search bar */}
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search documents by name, type, or subject..."
              className="h-10 pl-9 text-sm"
              autoFocus
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute top-1/2 right-3 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
              >
                Clear
              </button>
            )}
          </div>

          {/* Filter Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
            <TabsList className="w-full">
              <TabsTrigger value="all" className="flex-1">
                All Documents ({docs.length})
              </TabsTrigger>
              <TabsTrigger value="pdf" className="flex-1">
                PDFs & Texts ({pdfCount})
              </TabsTrigger>
              <TabsTrigger value="images" className="flex-1">
                Images ({imageCount})
              </TabsTrigger>
              <TabsTrigger value="upload" className="flex-1">
                <CloudUpload className="mr-1.5 h-3.5 w-3.5" />
                Upload New
              </TabsTrigger>
            </TabsList>

            <div className="mt-4 max-h-[380px] overflow-y-auto pb-6">
              {activeTab === "upload" ? (
                <div className="pt-2">
                  <UploadDropzone
                    onFiles={(files) => {
                      onUploadFiles(files);
                      setActiveTab("all");
                    }}
                  />
                </div>
              ) : (
                <>
                  {filteredDocs.length === 0 ? (
                    <div className="py-12 text-center">
                      <FileText className="mx-auto h-10 w-10 text-muted-foreground/40" />
                      <p className="mt-3 text-sm font-medium text-foreground">
                        {query ? "No documents match your search query." : "No documents uploaded yet."}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {query
                          ? "Try a different search term or check spelling."
                          : "Upload question papers, textbooks, or notes to get started."}
                      </p>
                      <Button
                        size="sm"
                        className="mt-4 gradient-brand text-brand-foreground"
                        onClick={() => setActiveTab("upload")}
                      >
                        <CloudUpload className="mr-1.5 h-4 w-4" />
                        Upload Document
                      </Button>
                    </div>
                  ) : (
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      {filteredDocs.map((doc) => {
                        const Icon = iconMap[doc.kind] || FileText;
                        return (
                          <div
                            key={doc.id}
                            className="group flex flex-col justify-between rounded-xl border border-border/70 bg-card/60 p-3 transition-all hover:border-primary/40 hover:bg-card"
                          >
                            <div className="flex items-start gap-3">
                              {doc.kind === "image" && doc.previewUrl ? (
                                <div className="h-12 w-12 shrink-0 overflow-hidden rounded-lg border bg-accent/30">
                                  <img
                                    src={doc.previewUrl}
                                    alt={doc.name}
                                    className="h-full w-full object-cover"
                                  />
                                </div>
                              ) : (
                                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent text-accent-foreground">
                                  <Icon className="h-5 w-5" />
                                </span>
                              )}
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-semibold text-foreground" title={doc.name}>
                                  {doc.name}
                                </p>
                                <p className="truncate text-[11px] text-muted-foreground">
                                  {doc.typeLabel}
                                </p>
                                <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                                  <span className="flex items-center gap-1">
                                    <Layers className="h-3 w-3" />
                                    {doc.pages} page{doc.pages === 1 ? "" : "s"}
                                  </span>
                                  <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    {formatTime(doc.uploadedAt)}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="mt-3 flex items-center justify-between border-t border-border/40 pt-2">
                              {onAskAboutDoc ? (
                                <button
                                  onClick={() => {
                                    onAskAboutDoc(doc.name);
                                    onOpenChange(false);
                                  }}
                                  className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                                >
                                  <Sparkles className="h-3 w-3" />
                                  Ask about this paper
                                </button>
                              ) : (
                                <span />
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => onDeleteDoc(doc.id)}
                                aria-label={`Delete ${doc.name}`}
                                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </div>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
}
