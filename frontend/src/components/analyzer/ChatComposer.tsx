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
      void processFile(files[0]);
      if (files.length > 1 && onFiles) {
        onFiles(files.slice(1));
      }
    }
  };

  const canSend = !loading && (value.trim().length > 0 || attachedFile !== null);

  return (
    <div className="relative z-20 px-3 pb-5 pt-2 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {/* Composer container with Drag-and-Drop */}
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`composer-pill relative rounded-2xl border transition-all duration-300 ${
            isDragging
              ? "border-sky-400 bg-sky-950/60 shadow-[0_0_35px_rgba(56,189,248,0.3)]"
              : "border-white/10 hover:border-sky-400/30"
          }`}
        >
          {/* Specular top highlight line */}
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-px"
            style={{
              background:
                "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 30%, rgba(56,189,248,0.35) 50%, rgba(255,255,255,0.15) 70%, transparent 100%)",
            }}
          />

          {/* Drag Overlay */}
          {isDragging && (
            <div className="absolute inset-0 z-50 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-sky-400 bg-slate-950/90 backdrop-blur-md pointer-events-none">
              <UploadCloud className="h-8 w-8 text-sky-400 animate-bounce mb-1" />
              <p className="text-sm font-semibold text-white">Drop question paper or screenshot here</p>
              <p className="text-xs text-sky-300 font-mono">PNG, JPG, WEBP, or PDF</p>
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
            <div className="mx-3 mt-2.5 flex items-center justify-between gap-3 rounded-xl border border-sky-400/25 bg-slate-900/80 p-2 shadow-md backdrop-blur-md">
              <div className="flex items-center gap-2.5 min-w-0">
                {attachedFile.type.startsWith("image/") ? (
                  <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-lg border border-white/10 bg-slate-950">
                    <img
                      src={attachedFile.previewUrl}
                      alt={attachedFile.name}
                      className="h-full w-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-sky-400/20 bg-sky-950/40 text-sky-400">
                    <FileText className="h-5 w-5" />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="truncate text-xs font-semibold text-slate-100 max-w-[200px] sm:max-w-[340px]">
                      {attachedFile.name}
                    </p>
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-mono uppercase bg-slate-800 text-sky-300">
                      {attachedFile.name.split(".").pop() || "file"}
                    </Badge>
                  </div>
                  <p className="text-[10px] font-mono text-slate-400 mt-0.5">
                    {(attachedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready for AI analysis
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={removeAttachment}
                className="h-7 w-7 rounded-lg text-slate-400 hover:bg-rose-950/40 hover:text-rose-300 flex items-center justify-center shrink-0 transition-colors"
                title="Remove attachment"
              >
                <X className="h-4 w-4" />
              </button>
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
                ? "Ask a question (e.g. 'Solve Q2', 'Solve all questions step by step')..."
                : "Ask anything about your question papers or syllabus... (Paste screenshots with Ctrl+V)"
            }
            className="max-h-48 min-h-[54px] resize-none border-0 bg-transparent px-4 py-3.5 text-[0.95rem] text-slate-100 shadow-none focus-visible:ring-0 placeholder:text-slate-500"
          />

          {/* Bottom toolbar */}
          <div className="flex items-center gap-1.5 px-3 pb-2.5">
            <button
              type="button"
              disabled={isProcessing}
              className="flex h-8 items-center gap-1.5 rounded-xl border border-white/5 bg-slate-900/40 px-2.5 text-xs text-slate-400 hover:border-sky-400/30 hover:bg-slate-800/60 hover:text-slate-200 transition-all cursor-pointer"
              onClick={() => docInput.current?.click()}
              title="Attach document (PDF, DOCX, TXT)"
            >
              <Paperclip className="h-3.5 w-3.5 text-sky-400" />
              <span className="hidden sm:inline">Attach Doc</span>
            </button>

            <button
              type="button"
              disabled={isProcessing}
              className="flex h-8 items-center gap-1.5 rounded-xl border border-white/5 bg-slate-900/40 px-2.5 text-xs text-slate-400 hover:border-sky-400/30 hover:bg-slate-800/60 hover:text-slate-200 transition-all cursor-pointer"
              onClick={() => imageInput.current?.click()}
              title="Upload question paper photo or screenshot"
            >
              <ImagePlus className="h-3.5 w-3.5 text-indigo-400" />
              <span className="hidden sm:inline">Add Image</span>
            </button>

            {isProcessing && (
              <span className="flex items-center gap-1.5 text-[11px] text-sky-300 font-mono animate-pulse ml-2">
                <Loader2 className="h-3 w-3 animate-spin" />
                Reading file…
              </span>
            )}

            {/* Keyboard hint */}
            <span className="ml-auto mr-2 hidden text-[11px] font-mono text-slate-500 sm:inline">
              ⏎ send · Ctrl+V paste
            </span>

            {/* Send / Stop button */}
            <div>
              {loading ? (
                <button
                  aria-label="Stop generating"
                  onClick={onStop}
                  className="flex h-8.5 w-8.5 shrink-0 items-center justify-center rounded-xl bg-rose-500 text-white shadow-lg transition-transform hover:bg-rose-600 active:scale-90 cursor-pointer"
                >
                  <Square className="h-3 w-3 fill-current" />
                </button>
              ) : (
                <button
                  aria-label="Send message"
                  disabled={!canSend}
                  onClick={handleSend}
                  className="flex h-8.5 w-8.5 shrink-0 items-center justify-center rounded-xl border border-sky-400/40 bg-gradient-to-br from-sky-400 to-indigo-500 text-slate-950 shadow-[0_0_20px_rgba(56,189,248,0.35)] transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100 disabled:cursor-not-allowed cursor-pointer"
                >
                  <ArrowUp className="h-4 w-4 stroke-[2.5]" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Footer disclaimer */}
        <p className="mt-2 text-center text-[10px] font-mono text-slate-500">
          SS SPARK · Grounded in your uploaded exam papers, textbooks & syllabi
        </p>
      </div>
    </div>
  );
}
