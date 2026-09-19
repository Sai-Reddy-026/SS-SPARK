import { memo, useState } from "react";
import {
  AlertCircle,
  BadgeCheck,
  ChevronDown,
  Clock,
  Copy,
  FileText,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatTime, type ChatMessageData } from "@/lib/analyzer";
import { Markdown } from "./Markdown";
import { CitationCard, SourceCard } from "./CitationCard";
import { SparkCore } from "@/components/astra/SparkCore";

export const ChatMessage = memo(function ChatMessage({
  message,
  onRegenerate,
}: {
  message: ChatMessageData;
  onRegenerate: () => void;
}) {
  const [contextOpen, setContextOpen] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const isUser = message.role === "user";

  // ─── User message — right-aligned pill bubble ───
  if (isUser) {
    return (
      <div className="animate-message-in flex justify-end px-2 sm:px-4">
        <div className="flex max-w-[85%] flex-col items-end gap-1.5 sm:max-w-[70%]">
          {message.attachment && (
            <div className="overflow-hidden rounded-2xl border border-sky-400/20 bg-slate-900/60 p-1.5 shadow-md backdrop-blur-md">
              {message.attachment.type?.startsWith("image/") || message.attachment.previewUrl ? (
                <div className="group relative max-h-56 max-w-xs overflow-hidden rounded-xl border border-white/10 bg-slate-950">
                  <img
                    src={message.attachment.previewUrl || message.attachment.dataUrl}
                    alt={message.attachment.name}
                    className="h-auto max-h-52 w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-2 text-left">
                    <p className="truncate text-xs font-medium text-white">{message.attachment.name}</p>
                    <p className="text-[10px] text-white/70">
                      {(message.attachment.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2 px-3 py-2 text-xs text-sky-200">
                  <FileText className="h-4 w-4 text-sky-400" />
                  <span className="max-w-[180px] truncate font-medium">{message.attachment.name}</span>
                </div>
              )}
            </div>
          )}
          <div className="user-bubble rounded-3xl rounded-br-md px-4.5 py-3 text-[0.95rem] leading-relaxed text-slate-100 shadow-md">
            {message.content}
          </div>
          <p className="flex items-center gap-1 pr-1 text-[10px] font-mono text-slate-500">
            <Clock className="h-3 w-3" />
            {formatTime(message.createdAt)}
          </p>
        </div>
      </div>
    );
  }

  // ─── Assistant error message ───
  if (message.status === "error") {
    return (
      <div className="animate-message-in px-2 sm:px-4">
        <div className="mx-auto flex max-w-3xl gap-4">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 shadow-md mt-1">
            <AlertCircle className="h-4 w-4" />
          </span>
          <div className="flex-1 pb-2">
            <div className="rounded-2xl border border-rose-500/30 bg-rose-950/20 px-4 py-3 backdrop-blur-md">
              <p className="text-sm font-semibold text-rose-300 mb-1">Unable to respond</p>
              <p className="text-xs text-rose-300/80 leading-relaxed">{message.content}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={onRegenerate}
                className="mt-2.5 h-7 gap-1.5 px-2.5 text-xs text-rose-300 hover:text-rose-200 hover:bg-rose-900/30"
              >
                <RefreshCw className="h-3 w-3" />
                Retry Question
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── Assistant message — Astra-styled Left-aligned response ───
  return (
    <div className="animate-message-in group px-2 sm:px-4">
      <div className="mx-auto flex max-w-3xl gap-4">
        {/* Astra Spark Core Avatar */}
        <div className="flex shrink-0 flex-col items-center gap-2 pt-1">
          <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-sky-400/30 bg-slate-950/80 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
            <SparkCore variant="compact" />
          </div>
        </div>

        {/* Content Body */}
        <div className="min-w-0 flex-1 pb-2">
          {/* Header row: Model label + confidence rating */}
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
              SS SPARK <span className="text-sky-400">NEURAL</span>
            </span>

            {message.status === "general" ? (
              <Badge
                variant="outline"
                className="gap-1 text-[10px] font-mono border-indigo-400/30 text-indigo-300 bg-indigo-950/30"
              >
                <Wand2 className="h-3 w-3" />
                General AI
              </Badge>
            ) : (
              message.confidence !== undefined &&
              message.confidence !== null && (
                <Badge
                  variant="secondary"
                  className={cn(
                    "gap-1 text-[10px] font-mono border bg-slate-950/50",
                    message.confidence >= 0.8
                      ? "border-emerald-500/30 text-emerald-300"
                      : message.confidence >= 0.6
                      ? "border-amber-500/30 text-amber-300"
                      : "border-rose-500/30 text-rose-300"
                  )}
                >
                  <BadgeCheck className="h-3 w-3" />
                  {Math.round(message.confidence * 100)}% Document Grounding
                </Badge>
              )
            )}

            <span className="ml-auto flex items-center gap-1 text-[10px] font-mono text-slate-500">
              <Clock className="h-3 w-3" />
              {formatTime(message.createdAt)}
            </span>
          </div>

          {/* Answer Markdown with streaming pulse */}
          <div className="relative text-slate-100 leading-relaxed text-[0.95rem]">
            <Markdown content={message.content} />
            {message.isStreaming && (
              <span className="ml-1 inline-block h-4 w-1 animate-pulse rounded-full bg-sky-400 shadow-[0_0_8px_#38bdf8] align-middle" />
            )}
          </div>

          {/* Citations & Source Documents */}
          {message.citations && message.citations.length > 0 && (
            <div className="mt-4 space-y-3 rounded-2xl border border-white/5 bg-slate-950/40 p-3.5 backdrop-blur-md">
              <div>
                <p className="mb-2 text-[10px] font-mono font-medium tracking-wider text-slate-400 uppercase">
                  Verified In Sources
                </p>
                <div className="flex flex-wrap gap-2">
                  {message.citations.map((citation, idx) => (
                    <SourceCard key={citation.id ?? `src-${idx}`} citation={citation} />
                  ))}
                </div>
              </div>

              <button
                onClick={() => setContextOpen((v) => !v)}
                className="flex items-center gap-1.5 text-[10px] font-mono font-medium tracking-wider text-sky-400 hover:text-sky-300 transition-colors uppercase cursor-pointer"
              >
                <ChevronDown
                  className={cn("h-3.5 w-3.5 transition-transform", contextOpen && "rotate-180")}
                />
                Retrieved Context Snippets ({message.citations.length})
              </button>

              {contextOpen && (
                <div className="animate-message-in grid gap-2 sm:grid-cols-2 pt-1">
                  {message.citations.map((citation, idx) => (
                    <CitationCard key={citation.id ?? `ctx-${idx}`} citation={citation} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Action Row on Hover */}
          {!message.isStreaming && (
            <div className="mt-3 flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
              <ActionButton
                label="Copy"
                icon={Copy}
                onClick={() => {
                  void navigator.clipboard?.writeText(message.content);
                  toast.success("Answer copied to clipboard");
                }}
              />
              <ActionButton label="Regenerate" icon={RefreshCw} onClick={onRegenerate} />
              <ActionButton
                label="Helpful"
                icon={ThumbsUp}
                active={vote === "up"}
                onClick={() => {
                  setVote("up");
                  toast.success("Feedback recorded");
                }}
              />
              <ActionButton
                label="Not helpful"
                icon={ThumbsDown}
                active={vote === "down"}
                onClick={() => {
                  setVote("down");
                  toast.success("Feedback recorded");
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

function ActionButton({
  label,
  icon: Icon,
  onClick,
  active,
}: {
  label: string;
  icon: typeof Copy;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={cn(
        "flex h-7 items-center gap-1 rounded-lg border border-white/5 bg-slate-900/50 px-2 text-[11px] text-slate-400 transition-all hover:border-sky-400/30 hover:bg-slate-800/80 hover:text-slate-200 cursor-pointer",
        active && "border-sky-400/50 bg-sky-950/60 text-sky-300",
      )}
    >
      <Icon className="h-3 w-3" />
      <span>{label}</span>
    </button>
  );
}

export function TypingIndicator({ phase }: { phase?: string }) {
  return (
    <div className="animate-message-in px-2 sm:px-4">
      <div className="mx-auto flex max-w-3xl items-center gap-3">
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-sky-400/30 bg-slate-950/80 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
          <SparkCore variant="compact" />
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-sky-400/20 bg-slate-900/60 px-4 py-2 text-xs text-sky-200 shadow-md backdrop-blur-md">
          <div className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:0ms]" />
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-bounce [animation-delay:300ms]" />
          </div>
          <span className="font-mono text-[11px]">
            {phase ? phase : "Analyzing documents & generating solution…"}
          </span>
        </div>
      </div>
    </div>
  );
}
