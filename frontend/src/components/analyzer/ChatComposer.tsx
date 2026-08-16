import { useRef } from "react";
import { ArrowUp, ImagePlus, Paperclip, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onFiles: (files: File[]) => void;
  loading: boolean;
}

export function ChatComposer({ value, onChange, onSend, onStop, onFiles, loading }: ChatComposerProps) {
  const docInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);

  return (
    <div className="border-t border-border/30 bg-background/70 px-3 pb-4 pt-3 backdrop-blur-xl sm:px-5">
      <div className="mx-auto max-w-3xl">
        {/* Composer pill — Ultra-Premium Obsidian Glass Design */}
        <div className="relative rounded-2xl border border-white/10 bg-[#181822]/90 dark:bg-[#16161f]/90 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.36)] transition-all duration-200 hover:border-white/15 focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/20">
          {/* Hidden file inputs */}
          <input
            ref={docInput}
            type="file"
            multiple
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={(event) => {
              onFiles(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
          />
          <input
            ref={imageInput}
            type="file"
            multiple
            accept=".png,.jpg,.jpeg"
            className="hidden"
            onChange={(event) => {
              onFiles(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
          />

          {/* Textarea */}
          <Textarea
            id="chat-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (!loading && value.trim()) onSend();
              }
            }}
            rows={1}
            placeholder="Ask anything about your uploaded question papers..."
            className="max-h-48 min-h-[54px] resize-none border-0 bg-transparent px-4 py-3.5 text-[0.95rem] text-foreground shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/60"
          />

          {/* Bottom toolbar */}
          <div className="flex items-center gap-1.5 px-3 pb-2.5">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 rounded-xl px-2.5 text-xs text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
              onClick={() => docInput.current?.click()}
              title="Attach document (PDF, DOCX, TXT)"
            >
              <Paperclip className="h-4 w-4" />
              <span className="hidden sm:inline">Attach</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 rounded-xl px-2.5 text-xs text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
              onClick={() => imageInput.current?.click()}
              title="Upload paper image"
            >
              <ImagePlus className="h-4 w-4" />
              <span className="hidden sm:inline">Image</span>
            </Button>

            {/* Send / Stop button */}
            <div className="ml-auto">
              {loading ? (
                <Button
                  size="icon"
                  aria-label="Stop generating"
                  onClick={onStop}
                  className="h-9 w-9 shrink-0 rounded-xl bg-foreground text-background shadow-sm hover:bg-foreground/90"
                >
                  <Square className="h-3.5 w-3.5 fill-current" />
                </Button>
              ) : (
                <Button
                  size="icon"
                  aria-label="Send message"
                  disabled={!value.trim()}
                  onClick={onSend}
                  className="h-9 w-9 shrink-0 rounded-xl gradient-brand text-brand-foreground shadow-[0_2px_12px_rgba(139,92,246,0.35)] transition-all hover:scale-105 hover:shadow-[0_4px_20px_rgba(139,92,246,0.5)] active:scale-95 disabled:opacity-35 disabled:hover:scale-100 disabled:hover:shadow-none"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Footer disclaimer */}
        <p className="mt-2 text-center text-[11px] text-muted-foreground/60">
          SS Spark · Answers grounded only in your uploaded documents. Verify before exams.
        </p>
      </div>
    </div>
  );
}
