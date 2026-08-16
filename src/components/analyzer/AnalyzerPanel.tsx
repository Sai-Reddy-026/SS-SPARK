import React, { useEffect, useState } from "react";
import { X, FileStack, HelpCircle, TrendingUp, Repeat, Loader2 } from "lucide-react";
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

export function AnalyzerPanel({
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
        "fixed inset-y-0 right-0 z-40 w-[340px] border-l bg-sidebar/90 backdrop-blur-xl transition-transform duration-300 ease-out xl:static xl:z-auto xl:translate-x-0 xl:transition-[width,opacity]",
        open ? "translate-x-0 xl:w-[350px] xl:opacity-100" : "translate-x-full xl:w-0 xl:opacity-0",
      )}
    >
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <p className="text-sm font-semibold">Paper Analyzer</p>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close analyzer panel">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {loading ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ScrollArea className="flex-1">
            <div className="space-y-4 p-4">
              <div className="grid grid-cols-2 gap-2">
                <Stat icon={FileStack} label="Uploaded papers" value={String(totalDocs)} />
                <Stat icon={HelpCircle} label="Total questions" value={String(totalQuestions)} />
              </div>

              <Section title="Frequently asked topics" icon={TrendingUp}>
                {topicData.length === 0 ? (
                  <p className="text-center text-[11px] text-muted-foreground py-6">
                    Ask questions to see topics appear here.
                  </p>
                ) : (
                  <div className="h-[150px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={topicData} layout="vertical" margin={{ left: -18, right: 8 }}>
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="topic"
                          width={104}
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

              <Section title="Subject distribution">
                {subjectData.length === 0 ? (
                  <p className="text-center text-[11px] text-muted-foreground py-6">
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
                    <div className="mt-1 flex flex-wrap gap-2">
                      {subjectData.map((entry, index) => (
                        <span
                          key={entry.name}
                          className="flex items-center gap-1.5 text-[11px] text-muted-foreground"
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

              <Section title="Exam year distribution">
                {yearData.length === 0 ? (
                  <p className="text-center text-[11px] text-muted-foreground py-6">
                    No year data yet. Upload exam papers to see trends.
                  </p>
                ) : (
                  <div className="h-[130px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={yearData} margin={{ left: -28, right: 8, top: 6 }}>
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
                          dot={{ r: 3, fill: "var(--chart-2)" }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Section>

              <Section title="Most repeated questions" icon={Repeat}>
                {repeatedQuestions.length === 0 ? (
                  <p className="text-center text-[11px] text-muted-foreground py-6">
                    Ask questions to see them tracked here.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {repeatedQuestions.map((item, i) => (
                      <div key={i} className="rounded-xl border bg-background/40 p-2.5">
                        <p className="text-xs leading-relaxed">{item.q}</p>
                        {item.years && (
                          <Badge variant="secondary" className="mt-1.5 text-[10px]">
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
}

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
    <div className="glass rounded-2xl p-3">
      <Icon className="h-4 w-4 text-primary" />
      <p className="mt-2 text-xl font-semibold">{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
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
    <div className="glass rounded-2xl p-3">
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        {Icon && <Icon className="h-3.5 w-3.5" />}
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
    <div className="glass-elevated rounded-lg px-2.5 py-1.5 text-[11px]">
      <p className="font-medium">{entry.name ?? label}</p>
      <p className="text-muted-foreground">{entry.value}</p>
    </div>
  );
}
