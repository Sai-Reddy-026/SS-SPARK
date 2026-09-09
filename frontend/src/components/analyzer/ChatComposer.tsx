import { useState, useRef, useCallback, useEffect } from "react";
import { ArrowUp, FileText, ImagePlus, Paperclip, Square, UploadCloud, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

export interface AttachedFile {
  file: File;
  name: string;
  type: string;
  size: number;
  previewUrl: string;
  dataUrl: string;
}

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text?: string, attachment?: AttachedFile | null) => void;
  onStop: () => void;
  onFiles?: (files: File[]) => void;
  loading: boolean;
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  onFiles,
  loading,
}: ChatComposerProps) {
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const docInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dragCounterRef = useRef(0);

  // Clean up blob URL on unmount or when attachment changes
  useEffect(() => {
    return () => {
      if (attachedFile?.previewUrl && attachedFile.previewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(attachedFile.previewUrl);
      }
    };
  }, [attachedFile]);

  const processFile = useCallback(async (file: File) => {
    if (file.size > 25 * 1024 * 1024) {
      toast.error("File exceeds 25 MB limit.");
      return;
    }

    setIsProcessing(true);
    try {
      const isImg = file.type.startsWith("image/") || /\.(png|jpe?g|webp)$/i.test(file.name);
      let previewUrl = "";
      if (isImg) {
        previewUrl = URL.createObjectURL(file);
      }

      // Convert file to Base64 data URL
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      // Revoke previous blob URL if any
      setAttachedFile((prev) => {
        if (prev?.previewUrl && prev.previewUrl.startsWith("blob:")) {
          URL.revokeObjectURL(prev.previewUrl);
        }
        return {
          file,
          name: file.name,
          type: file.type || (isImg ? "image/jpeg" : "application/pdf"),
          size: file.size,
          previewUrl: previewUrl || dataUrl,
          dataUrl,
        };
      });

      toast.success(`Attached "${file.name}"`);
      textareaRef.current?.focus();
    } catch (err) {
      toast.error("Failed to read file for attachment.");
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const removeAttachment = useCallback(() => {
    if (attachedFile?.previewUrl && attachedFile.previewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(attachedFile.previewUrl);
    }
    setAttachedFile(null);
  }, [attachedFile]);

  const handleSend = useCallback(() => {
    if (loading) return;
    const trimmed = value.trim();
    if (!trimmed && !attachedFile) return;

    const textToSend = trimmed || "Please solve and analyze the questions in this attached paper.";
    const currentAttachment = attachedFile;
    setAttachedFile(null);
    onSend(textToSend, currentAttachment);
  }, [loading, value, attachedFile, onSend]);

  // Clipboard paste listener (e.g. Ctrl+V screenshots)
  const handlePaste = useCallback(
    (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = event.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf("image") !== -1) {
          event.preventDefault();
          const file = item.getAsFile();
          if (file) {
            const ext = file.type.split("/")[1] || "png";
            const namedFile = new File([file], `screenshot_${Date.now()}.${ext}`, {
              type: file.type,
            });
            void processFile(namedFile);
            return;
          }
        }
      }
    },
    [processFile]
  );

  // Drag and Drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounterRef.current = 0;

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      // Attach the first file directly to composer
      void processFile(files[0]);
      // If multiple files dropped, also pass the rest to workspace docs
      if (files.length > 1 && onFiles) {
        onFiles(files.slice(1));
      }
    }
  };

  const canSend = !loading && (value.trim().length > 0 || attachedFile !== null);

  return (
    <div className="border-t border-border/20 bg-background/60 px-3 pb-4 pt-3 backdrop-blur-xl sm:px-5">
      <div className="mx-auto max-w-3xl">
        {/* Composer container with Drag-and-Drop */}
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`composer-pill premium-focus relative rounded-2xl border backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.2)] transition-all duration-200 ${
            isDragging ? "ring-2 ring-primary border-primary bg-primary/5" : ""
          }`}
        >
          {/* Drag Overlay */}
          {isDragging && (
            <div className="absolute inset-0 z-50 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-primary bg-background/90 backdrop-blur-md pointer-events-none">
              <UploadCloud className="h-8 w-8 text-primary animate-bounce mb-1" />
              <p className="text-sm font-semibold text-foreground">Drop question paper or screenshot here</p>
              <p className="text-xs text-muted-foreground">PNG, JPG, WEBP, or PDF</p>
            </div>
          )}

          {/* Hidden file inputs */}
          <input
            ref={docInput}
            type="file"
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void processFile(file);
              event.target.value = "";
            }}
          />
          <input
            ref={imageInput}
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void processFile(file);
              event.target.value = "";
            }}
          />

          {/* Inline Attachment Preview Card */}
          {attachedFile && (
            <div className="mx-3 mt-2.5 flex items-center justify-between gap-3 rounded-xl border border-border/50 bg-card/80 p-2 shadow-sm backdrop-blur-md animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center gap-2.5 min-w-0">
                {attachedFile.type.startsWith("image/") ? (
                  <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-lg border border-border/50 bg-muted">
                    <img
                      src={attachedFile.previewUrl}
                      alt={attachedFile.name}
                      className="h-full w-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-border/50 bg-primary/10 text-primary">
                    <FileText className="h-6 w-6" />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="truncate text-xs font-semibold text-foreground max-w-[200px] sm:max-w-[340px]">
                      {attachedFile.name}
                    </p>
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-mono uppercase">
                      {attachedFile.name.split(".").pop() || "file"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {(attachedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready for AI analysis
                  </p>
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={removeAttachment}
                className="h-7 w-7 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive shrink-0"
                title="Remove attachment"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Textarea */}
          <Textarea
            id="chat-input"
            ref={textareaRef}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onPaste={handlePaste}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSend();
              }
            }}
            rows={1}
            placeholder={
              attachedFile
                ? "Ask a question (e.g. 'Solve Q2', 'Solve all'), or press send..."
                : "Ask anything about your uploaded question papers... (Paste images with Ctrl+V)"
            }
            className="max-h-48 min-h-[54px] resize-none border-0 bg-transparent px-4 py-3.5 text-[0.95rem] text-foreground shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/50"
          />

          {/* Bottom toolbar */}
          <div className="flex items-center gap-1 px-3 pb-2.5">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isProcessing}
              className="h-8 gap-1.5 rounded-xl px-2.5 text-xs text-muted-foreground transition-all hover:bg-accent hover:text-foreground"
              onClick={() => docInput.current?.click()}
              title="Attach document (PDF, DOCX, TXT)"
            >
              <Paperclip className="h-4 w-4" />
              <span className="hidden sm:inline">Attach Doc</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isProcessing}
              className="h-8 gap-1.5 rounded-xl px-2.5 text-xs text-muted-foreground transition-all hover:bg-accent hover:text-foreground"
              onClick={() => imageInput.current?.click()}
              title="Upload question paper or screenshot"
            >
              <ImagePlus className="h-4 w-4" />
              <span className="hidden sm:inline">Add Image</span>
            </Button>

            {isProcessing && (
              <span className="flex items-center gap-1 text-[11px] text-muted-foreground animate-pulse ml-2">
                <Loader2 className="h-3 w-3 animate-spin" />
                Reading file...
              </span>
            )}

            {/* Keyboard hint */}
            <span className="ml-auto mr-2 hidden text-[11px] text-muted-foreground/40 sm:inline">
              ⏎ to send · Ctrl+V to paste
            </span>

            {/* Send / Stop button */}
            <div>
              {loading ? (
                <Button
                  size="icon"
                  aria-label="Stop generating"
                  onClick={onStop}
                  className="h-9 w-9 shrink-0 rounded-xl bg-foreground text-background shadow-sm transition-transform hover:bg-foreground/90 active:scale-90"
                >
                  <Square className="h-3.5 w-3.5 fill-current" />
                </Button>
              ) : (
                <Button
                  size="icon"
                  aria-label="Send message"
                  disabled={!canSend}
                  onClick={handleSend}
                  className="h-9 w-9 shrink-0 rounded-xl gradient-brand text-brand-foreground shadow-[0_2px_12px_color-mix(in_oklab,var(--brand)_35%,transparent)] transition-all duration-200 hover:scale-105 hover:shadow-[0_4px_20px_color-mix(in_oklab,var(--brand)_50%,transparent)] active:scale-95 disabled:opacity-30 disabled:hover:scale-100 disabled:hover:shadow-none"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Footer disclaimer */}
        <p className="mt-2.5 text-center text-[11px] text-muted-foreground/40">
          SS Spark · Question Paper AI with Step-by-Step Solutions & Mathematical Formula Precision
        </p>
      </div>
    </div>
  );
}
