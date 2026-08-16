import { useRef, useState } from "react";
import { CloudUpload, FileImage, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void;
  compact?: boolean;
}

export function UploadDropzone({ onFiles, compact }: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        onFiles(Array.from(event.dataTransfer.files));
      }}
      className={cn(
        "relative overflow-hidden rounded-2xl border-2 border-dashed text-center transition-all duration-300",
        compact ? "p-5" : "p-8",
        dragging
          ? "border-primary bg-primary/10 scale-[1.01]"
          : "border-border bg-background/40 hover:border-primary/60",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
        className="hidden"
        onChange={(event) => {
          onFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl gradient-brand text-brand-foreground shadow-lg">
        <CloudUpload className="h-6 w-6" />
      </span>
      <p className="mt-3 text-sm font-semibold">Drag & drop your files here</p>
      <p className="mt-1 text-xs text-muted-foreground">
        PDF, DOCX, TXT, PNG, JPG, JPEG · up to 25 MB each
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <Button
          onClick={() => inputRef.current?.click()}
          className="gradient-brand text-brand-foreground hover-lift"
        >
          <FileText className="h-4 w-4" />
          Upload Documents
        </Button>
        <Button variant="secondary" onClick={() => inputRef.current?.click()}>
          <FileImage className="h-4 w-4" />
          Upload Image
        </Button>
      </div>
    </div>
  );
}
