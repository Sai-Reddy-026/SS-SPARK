import { useState } from "react";
import {
  BadgeCheck,
  BrainCircuit,
  ChevronDown,
  Clock,
  Copy,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatTime, type ChatMessageData } from "@/lib/analyzer";
import { Markdown } from "./Markdown";
import { CitationCard, SourceCard } from "./CitationCard";

export function ChatMessage({
  message,
  onRegenerate,
}: {
  message: ChatMessageData;
  onRegenerate: () => void;
}) {
  const [contextOpen, setContextOpen] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const isUser = message.role === "user";

  // ─── User message — right-aligned pill bubble (ChatGPT style) ───
  if (isUser) {
    return (
      <div className="animate-message-in flex justify-end px-2 sm:px-4">
        <div className="flex max-w-[80%] flex-col items-end gap-1 sm:max-w-[65%]">
          <div className="rounded-3xl rounded-br-md bg-[#2f2f2f] dark:bg-[#2f2f2f] light:bg-[#ececec] px-4 py-3 text-[0.95rem] leading-relaxed text-foreground shadow-sm">
            {message.content}
          </div>
          <p className="flex items-center gap-1 pr-1 text-[11px] text-muted-foreground/70">
            <Clock className="h-3 w-3" />
            {formatTime(message.createdAt)}
          </p>
        </div>
      </div>
    );
  }

  // ─── Assistant message — left-aligned, full-width, no card (ChatGPT style) ───
  return (
    <div className="animate-message-in group px-2 sm:px-4">
      <div className="mx-auto flex max-w-3xl gap-4">
        {/* AI Avatar */}
        <div className="flex shrink-0 flex-col items-center gap-2 pt-1">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full gradient-brand text-brand-foreground shadow-md">
            <BrainCircuit className="h-4 w-4" />
          </span>
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1 pb-2">
          {/* Model label + confidence / mode badge */}
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-semibold text-foreground">SS SPARK AI</span>
            {message.status === "general" ? (
              <Badge
                variant="outline"
                className="gap-1 text-[11px] border-chart-2/50 text-chart-2"
              >
                <Wand2 className="h-3 w-3" />
                General AI answer
              </Badge>
            ) : (
              message.confidence !== undefined &&
              message.confidence !== null && (
                <Badge variant="secondary" className="gap-1 text-[11px]">
                  <BadgeCheck className="h-3 w-3 text-chart-5" />
                  {Math.round(message.confidence * 100)}% confidence
                </Badge>
              )
            )}
            <span className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground/70">
              <Clock className="h-3 w-3" />
              {formatTime(message.createdAt)}
            </span>
          </div>

          {/* Answer body */}
          <Markdown content={message.content} />

          {/* Citations */}
          {message.citations && message.citations.length > 0 && (
            <div className="mt-4 space-y-3 border-t border-border/50 pt-3">
              <div>
                <p className="mb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                  Source documents
                </p>
                <div className="flex flex-wrap gap-2">
                  {message.citations.map((citation, idx) => (
                    <SourceCard key={citation.id ?? `src-${idx}`} citation={citation} />
                  ))}
                </div>
              </div>

              <button
                onClick={() => setContextOpen((v) => !v)}
                className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase transition-colors hover:text-foreground"
              >
                <ChevronDown
                  className={cn("h-3.5 w-3.5 transition-transform", contextOpen && "rotate-180")}
                />
                Retrieved context ({message.citations.length})
              </button>

              {contextOpen && (
                <div className="animate-message-in grid gap-2 sm:grid-cols-2">
                  {message.citations.map((citation, idx) => (
                    <CitationCard key={citation.id ?? `ctx-${idx}`} citation={citation} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Action row — visible on hover (ChatGPT style) */}
          <div className="mt-2 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
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
              label="Like"
              icon={ThumbsUp}
              active={vote === "up"}
              onClick={() => {
                setVote("up");
                toast.success("Thanks for the feedback");
              }}
            />
            <ActionButton
              label="Dislike"
              icon={ThumbsDown}
              active={vote === "down"}
              onClick={() => {
                setVote("down");
                toast("Feedback noted — we'll improve retrieval");
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

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
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      aria-label={label}
      className={cn(
        "h-8 gap-1.5 px-2 text-[11px] text-muted-foreground hover:text-foreground",
        active && "text-primary",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">{label}</span>
    </Button>
  );
}

// ─── Typing Indicator — ChatGPT-style animated dots only ───
export function TypingIndicator() {
  return (
    <div className="animate-message-in px-2 sm:px-4">
      <div className="mx-auto flex max-w-3xl gap-4">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full gradient-brand text-brand-foreground shadow-md mt-1">
          <BrainCircuit className="h-4 w-4" />
        </span>
        <div className="flex-1 pb-2">
          <div className="mb-2">
            <span className="text-[13px] font-semibold text-foreground">SS SPARK AI</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Thinking</span>
            <span className="flex gap-1">
              <Dot delay="0s" />
              <Dot delay="0.2s" />
              <Dot delay="0.4s" />
            </span>
          </div>
          {/* Skeleton preview rows */}
          <div className="mt-3 space-y-2">
            <Skeleton className="h-3 w-3/4 rounded-full" />
            <Skeleton className="h-3 w-full rounded-full" />
            <Skeleton className="h-3 w-5/6 rounded-full" />
          </div>
        </div>
      </div>
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="animate-dot h-1.5 w-1.5 rounded-full bg-primary"
      style={{ animationDelay: delay }}
    />
  );
}

export function LoadingSpinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary/30 border-t-primary",
        className,
      )}
    />
  );
}
