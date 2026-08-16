import { FileImage, FileText, FileType2, Trash2, Clock, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatTime, type UploadedDoc } from "@/lib/analyzer";

const iconFor = {
  pdf: FileText,
  docx: FileType2,
  txt: FileType2,
  image: FileImage,
};

export function UploadCard({ doc, onDelete }: { doc: UploadedDoc; onDelete: () => void }) {
  const Icon = iconFor[doc.kind];
  return (
    <div className="animate-message-in glass hover-lift group flex items-start gap-3 rounded-2xl p-3">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent text-accent-foreground">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{doc.name}</p>
        <p className="truncate text-[11px] text-muted-foreground">{doc.typeLabel}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Layers className="h-3 w-3" />
            {doc.pages} pages
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatTime(doc.uploadedAt)}
          </span>
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={onDelete}
        aria-label={`Delete ${doc.name}`}
        className="shrink-0 text-muted-foreground hover:text-destructive"
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function ImagePreviewCard({ doc, onDelete }: { doc: UploadedDoc; onDelete: () => void }) {
  return (
    <div className="animate-message-in glass hover-lift group overflow-hidden rounded-2xl">
      <div className="relative grid h-28 place-items-center bg-accent/50">
        {doc.previewUrl ? (
          <img src={doc.previewUrl} alt={doc.name} className="h-full w-full object-cover" />
        ) : (
          <FileImage className="h-8 w-8 text-muted-foreground" />
        )}
        <Button
          variant="secondary"
          size="icon"
          onClick={onDelete}
          aria-label={`Delete ${doc.name}`}
          className="absolute top-2 right-2 h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="p-2.5">
        <p className="truncate text-xs font-medium">{doc.name}</p>
        <p className="truncate text-[11px] text-muted-foreground">
          Scanned paper · {formatTime(doc.uploadedAt)}
        </p>
      </div>
    </div>
  );
}
