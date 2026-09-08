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
      <DialogContent className="max-w-3xl overflow-hidden p-0 sm:rounded-3xl border-border/70 bg-card/95 backdrop-blur-2xl shadow-2xl">
        <DialogHeader className="border-b border-border/50 px-6 pt-6 pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2.5 text-xl font-bold tracking-tight">
              <span className="grid h-9 w-9 place-items-center rounded-xl gradient-brand text-brand-foreground shadow-md shadow-primary/20">
                <Search className="h-4.5 w-4.5" />
              </span>
              <span>Search Pad & Document Workspace</span>
            </DialogTitle>
            <Badge variant="secondary" className="gap-1.5 text-xs px-2.5 py-1">
              <Sparkles className="h-3 w-3 text-primary" />
              {docs.length} Document{docs.length === 1 ? "" : "s"}
            </Badge>
          </div>
        </DialogHeader>

        <div className="px-6 pt-4">
          {/* Search bar */}
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search documents by name, type, or subject..."
              className="h-11 pl-10 pr-16 text-sm bg-background/50 border-border/70 focus:border-primary focus:ring-2 focus:ring-primary/20 rounded-xl"
              autoFocus
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute top-1/2 right-3 -translate-y-1/2 rounded-md px-2 py-0.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {/* Filter Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
            <TabsList className="w-full h-11 p-1 bg-secondary/50 rounded-xl">
              <TabsTrigger value="all" className="flex-1 rounded-lg text-xs font-medium">
                All Documents ({docs.length})
              </TabsTrigger>
              <TabsTrigger value="pdf" className="flex-1 rounded-lg text-xs font-medium">
                PDFs & Notes ({pdfCount})
              </TabsTrigger>
              <TabsTrigger value="images" className="flex-1 rounded-lg text-xs font-medium">
                Images ({imageCount})
              </TabsTrigger>
              <TabsTrigger value="upload" className="flex-1 rounded-lg text-xs font-medium gap-1">
                <CloudUpload className="h-3.5 w-3.5 text-primary" />
                Upload New
              </TabsTrigger>
            </TabsList>

            <div className="mt-4 max-h-[390px] overflow-y-auto pb-6 pr-0.5">
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
                    <div className="py-14 text-center">
                      <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-secondary/50 text-muted-foreground">
                        <FileText className="h-6 w-6" />
                      </div>
                      <p className="text-sm font-semibold text-foreground">
                        {query ? "No documents match your search query." : "No documents uploaded yet."}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground max-w-xs mx-auto">
                        {query
                          ? "Try a different search term or clear the filter."
                          : "Upload question papers, textbooks, or syllabus notes to get cited AI answers."}
                      </p>
                      <Button
                        size="sm"
                        className="mt-4 gradient-brand text-brand-foreground shadow-md shadow-primary/20 hover-lift cursor-pointer"
                        onClick={() => setActiveTab("upload")}
                      >
                        <CloudUpload className="mr-1.5 h-4 w-4" />
                        Upload Document
                      </Button>
                    </div>
                  ) : (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {filteredDocs.map((doc) => {
                        const Icon = iconMap[doc.kind] || FileText;
                        const isPdf = doc.kind === "pdf";
                        const isImage = doc.kind === "image";

                        return (
                          <div
                            key={doc.id}
                            className="group relative flex flex-col justify-between rounded-2xl border border-border/60 bg-card/60 p-3.5 transition-all duration-200 hover:border-primary/40 hover:bg-card hover-glow hover:-translate-y-0.5"
                          >
                            <div className="flex items-start gap-3">
                              {isImage && doc.previewUrl ? (
                                <div className="h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-border/50 bg-accent/30 shadow-xs">
                                  <img
                                    src={doc.previewUrl}
                                    alt={doc.name}
                                    className="h-full w-full object-cover"
                                  />
                                </div>
                              ) : (
                                <span
                                  className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl shadow-xs ${
                                    isPdf
                                      ? "bg-primary/10 text-primary border border-primary/20"
                                      : "bg-chart-2/10 text-chart-2 border border-chart-2/20"
                                  }`}
                                >
                                  <Icon className="h-5 w-5" />
                                </span>
                              )}
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-semibold text-foreground group-hover:text-primary transition-colors" title={doc.name}>
                                  {doc.name}
                                </p>
                                <p className="truncate text-[11px] text-muted-foreground/80 mt-0.5">
                                  {doc.typeLabel}
                                </p>
                                <div className="mt-1.5 flex flex-wrap items-center gap-2.5 text-[11px] text-muted-foreground/60">
                                  <span className="flex items-center gap-1">
                                    <Layers className="h-3 w-3" />
                                    {doc.pages} page{doc.pages === 1 ? "" : "s"}
                                  </span>
                                  <span>·</span>
                                  <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    {formatTime(doc.uploadedAt)}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="mt-3.5 flex items-center justify-between border-t border-border/40 pt-2.5">
                              {onAskAboutDoc ? (
                                <button
                                  onClick={() => {
                                    onAskAboutDoc(doc.name);
                                    onOpenChange(false);
                                  }}
                                  className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline cursor-pointer"
                                >
                                  <Sparkles className="h-3.5 w-3.5" />
                                  <span>Ask about this</span>
                                </button>
                              ) : (
                                <span />
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => onDeleteDoc(doc.id)}
                                aria-label={`Delete ${doc.name}`}
                                className="h-7 w-7 text-muted-foreground/70 hover:text-destructive hover:bg-destructive/10 transition-colors"
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
