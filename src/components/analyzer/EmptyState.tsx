import { FileSearch, Sparkles, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UploadDropzone } from "./UploadDropzone";

export function EmptyState({ onFiles }: { onFiles: (files: File[]) => void }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-10 text-center">
      <div className="relative">
        <span className="absolute inset-0 -z-10 rounded-full blur-3xl gradient-brand opacity-30" />
        <span className="grid h-24 w-24 place-items-center rounded-3xl glass-elevated">
          <FileSearch className="h-11 w-11 text-primary" />
        </span>
      </div>
      <h2 className="mt-6 text-2xl font-semibold">
        <span className="gradient-text">Upload question papers or notes</span> to begin asking
        AI-powered questions.
      </h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Every answer stays grounded in your own material — with confidence scores, source documents
        and page numbers.
      </p>

      <div className="mt-6 w-full">
        <UploadDropzone onFiles={onFiles} />
      </div>

      <div className="mt-6 grid w-full gap-2 sm:grid-cols-3">
        {["Previous question papers", "Notes & textbooks", "Photos of handwritten papers"].map(
          (item) => (
            <div
              key={item}
              className="glass flex items-center gap-2 rounded-xl px-3 py-2.5 text-left text-xs text-muted-foreground"
            >
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-chart-2" />
              {item}
            </div>
          ),
        )}
      </div>
    </div>
  );
}

export function EmptyStateCompact({ onUpload }: { onUpload: () => void }) {
  return (
    <Button onClick={onUpload} className="gradient-brand text-brand-foreground hover-lift">
      <Upload className="h-4 w-4" />
      Upload Documents
    </Button>
  );
}
