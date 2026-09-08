import React, { memo, useEffect, useState } from "react";
import { X, FileStack, HelpCircle, TrendingUp, Repeat, Loader2, Sparkles } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { analyticsApi, type PanelStats } from "@/lib/api";

const pieColors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)"];

export const AnalyzerPanel = memo(function AnalyzerPanel({
  open,
  onClose,
  paperCount,
}: {
  open: boolean;
  onClose: () => void;
  paperCount: number;
}) {
  const [stats, setStats] = useState<PanelStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    analyticsApi
      .panelStats()
      .then((res) => {
        if (res.success) setStats(res.data);
      })
      .catch(() => {
        // silently fail — charts just show empty state
      })
      .finally(() => setLoading(false));
  }, [open]);

  const topicData = stats?.topic_data ?? [];
  const subjectData = stats?.subject_data ?? [];
  const yearData = stats?.year_data ?? [];
  const repeatedQuestions = stats?.recent_questions ?? [];
  const totalDocs = stats?.total_documents ?? paperCount;
  const totalQuestions = stats?.total_questions ?? 0;

  return (
    <aside
      className={cn(
        "fixed inset-y-0 right-0 z-40 w-[350px] border-l border-border/60 bg-sidebar/95 backdrop-blur-2xl transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] xl:static xl:z-auto xl:translate-x-0 xl:transition-[width,opacity]",
        open ? "translate-x-0 xl:w-[360px] xl:opacity-100" : "translate-x-full xl:w-0 xl:opacity-0",
      )}
    >
      <div className="flex h-full flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/50 px-5 py-3.5">
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg gradient-brand text-brand-foreground shadow-xs">
              <TrendingUp className="h-3.5 w-3.5" />
            </span>
            <p className="text-sm font-bold tracking-tight">Paper Analytics</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close analyzer panel" className="h-8 w-8 rounded-lg">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {loading ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : (
          <ScrollArea className="flex-1">
            <div className="space-y-4 p-4.5">
              {/* Quick stats */}
              <div className="grid grid-cols-2 gap-3">
                <Stat icon={FileStack} label="Uploaded papers" value={String(totalDocs)} />
                <Stat icon={HelpCircle} label="Total questions" value={String(totalQuestions)} />
              </div>

              {/* Topics bar chart */}
              <Section title="Frequently Asked Topics" icon={TrendingUp}>
                {topicData.length === 0 ? (
                  <p className="text-center text-xs text-muted-foreground/70 py-6">
                    Ask questions to see recurring topics appear here.
                  </p>
                ) : (
                  <div className="h-[155px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={topicData} layout="vertical" margin={{ left: -14, right: 8, top: 4, bottom: 4 }}>
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="topic"
                          width={105}
                          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip content={<ChartTip />} />
                        <Bar dataKey="count" radius={[0, 6, 6, 0]} fill="var(--chart-1)" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Section>

              {/* Subject distribution */}
              <Section title="Subject Distribution">
                {subjectData.length === 0 ? (
                  <p className="text-center text-xs text-muted-foreground/70 py-6">
                    Upload documents to see subject breakdown.
                  </p>
                ) : (
                  <>
                    <div className="h-[160px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={subjectData}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={38}
                            outerRadius={62}
                            paddingAngle={3}
                            stroke="none"
                          >
                            {subjectData.map((entry, index) => (
                              <Cell key={entry.name} fill={pieColors[index % pieColors.length]} />
                            ))}
                          </Pie>
                          <Tooltip content={<ChartTip />} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {subjectData.map((entry, index) => (
                        <span
                          key={entry.name}
                          className="flex items-center gap-1.5 rounded-md bg-secondary/40 px-2 py-0.5 text-[11px] text-muted-foreground"
                        >
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ background: pieColors[index % pieColors.length] }}
                          />
                          {entry.name} · {entry.value}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </Section>

              {/* Exam year trends */}
              <Section title="Exam Year Distribution">
                {yearData.length === 0 ? (
                  <p className="text-center text-xs text-muted-foreground/70 py-6">
                    No year data yet. Upload past papers to see year trends.
                  </p>
                ) : (
                  <div className="h-[135px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={yearData} margin={{ left: -28, right: 8, top: 8, bottom: 4 }}>
                        <XAxis
                          dataKey="year"
                          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip content={<ChartTip />} />
                        <Line
                          type="monotone"
                          dataKey="papers"
                          stroke="var(--chart-2)"
                          strokeWidth={2.5}
                          dot={{ r: 3.5, fill: "var(--chart-2)" }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Section>

              {/* Repeated questions */}
              <Section title="Most Repeated Questions" icon={Repeat}>
                {repeatedQuestions.length === 0 ? (
                  <p className="text-center text-xs text-muted-foreground/70 py-6">
                    Ask questions to see frequency insights here.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {repeatedQuestions.map((item, i) => (
                      <div key={i} className="rounded-xl border border-border/50 bg-card/60 p-3 transition-all hover:bg-card hover:border-primary/30">
                        <p className="text-xs leading-relaxed font-medium">{item.q}</p>
                        {item.years && (
                          <Badge variant="secondary" className="mt-2 text-[10px] bg-secondary/60">
                            {item.years}
                          </Badge>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            </div>
          </ScrollArea>
        )}
      </div>
    </aside>
  );
});

export default AnalyzerPanel;

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileStack;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/50 p-3.5 backdrop-blur-sm shadow-xs transition-all hover:border-primary/30 hover:bg-card">
      <div className="flex items-center justify-between">
        <Icon className="h-4 w-4 text-primary" />
        <Sparkles className="h-3 w-3 text-muted-foreground/30" />
      </div>
      <p className="mt-2 text-2xl font-bold tracking-tight text-foreground">{value}</p>
      <p className="text-[11px] text-muted-foreground/80 mt-0.5">{label}</p>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: typeof FileStack;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/50 p-3.5 backdrop-blur-sm shadow-xs">
      <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-muted-foreground/90 uppercase">
        {Icon && <Icon className="h-3.5 w-3.5 text-primary" />}
        {title}
      </p>
      {children}
    </div>
  );
}

function ChartTip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number | string }>;
  label?: string;
}) {
  const entry = payload?.[0];
  if (!active || !entry) return null;
  return (
    <div className="rounded-xl border border-border/80 bg-card/95 px-3 py-2 text-xs shadow-lg backdrop-blur-md">
      <p className="font-semibold text-foreground">{entry.name ?? label}</p>
      <p className="text-muted-foreground mt-0.5">{entry.value}</p>
    </div>
  );
}
