import { FileText, Quote } from "lucide-react";
import type { Citation } from "@/lib/analyzer";
import { Progress } from "@/components/ui/progress";

export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="rounded-xl border bg-background/40 p-3 transition-colors hover:border-primary/50">
      <div className="flex items-start gap-2">
        <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-chart-2" />
        <p className="min-w-0 text-xs leading-relaxed text-muted-foreground italic">
          {citation.snippet}
        </p>
      </div>
      <div className="mt-2.5 flex items-center gap-2 text-[11px] text-muted-foreground">
        <FileText className="h-3.5 w-3.5 shrink-0 text-chart-1" />
        <span className="truncate">{citation.source}</span>
        <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 font-mono">
          p.{citation.page}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Progress value={citation.relevance * 100} className="h-1" />
        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
          {Math.round(citation.relevance * 100)}%
        </span>
      </div>
    </div>
  );
}

export function SourceCard({ citation }: { citation: Citation }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-background/40 px-2.5 py-1.5 text-[11px] transition-colors hover:border-primary/50">
      <FileText className="h-3.5 w-3.5 shrink-0 text-chart-1" />
      <span className="max-w-[180px] truncate text-foreground/90">{citation.source}</span>
      <span className="shrink-0 text-muted-foreground">Page {citation.page}</span>
    </div>
  );
}
