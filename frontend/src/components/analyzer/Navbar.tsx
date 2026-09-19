import { memo } from "react";
import { BarChart3, Menu, Moon, Sun, Sparkles, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SparkCore } from "@/components/astra/SparkCore";

interface NavbarProps {
  onToggleSidebar: () => void;
  onTogglePanel: () => void;
  panelOpen: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  docCount: number;
  onOpenSearchPad?: () => void;
}

export const Navbar = memo(function Navbar({
  onToggleSidebar,
  onTogglePanel,
  panelOpen,
  theme,
  onToggleTheme,
  docCount,
  onOpenSearchPad,
}: NavbarProps) {
  return (
    <header className="relative z-20 flex items-center justify-between gap-3 px-4 py-3 bg-[rgba(6,10,22,0.65)] backdrop-blur-2xl border-b border-[rgba(255,255,255,0.06)] shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
      {/* Specular bottom highlight line */}
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(56,189,248,0.25) 25%, rgba(129,140,248,0.3) 50%, rgba(56,189,248,0.25) 75%, transparent 100%)",
        }}
      />

      {/* Left side: Sidebar Toggle & Brand Emblem */}
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/5 bg-slate-900/50 text-slate-400 hover:border-sky-400/30 hover:bg-slate-800/60 hover:text-white transition-all active:scale-95 cursor-pointer"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2.5 min-w-0">
          <SparkCore variant="compact" className="hidden sm:flex shrink-0" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-bold tracking-tight text-white font-display">
                SS SPARK <span className="text-sky-400 font-mono text-xs font-normal">AI WORKSPACE</span>
              </span>
            </div>
            <p className="hidden truncate text-[11px] text-slate-400 sm:block">
              Neural paper analysis & cited solutions
            </p>
          </div>
        </div>
      </div>

      {/* Right side: Search Pad trigger, theme, analytics panel toggle */}
      <div className="flex shrink-0 items-center gap-2">
        {/* Document Search Pad pill */}
        <button
          onClick={onOpenSearchPad}
          title="Open Document Search Pad"
          className="flex items-center gap-2 rounded-xl border border-sky-400/20 bg-sky-950/30 px-3 py-1.5 text-xs font-medium text-sky-200 transition-all hover:border-sky-400/50 hover:bg-sky-900/40 hover:shadow-[0_0_15px_rgba(56,189,248,0.15)] cursor-pointer"
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-sky-400" />
          </span>
          <span className="font-mono text-[11px] tracking-wide">
            {docCount} {docCount === 1 ? "SOURCE" : "SOURCES"}
          </span>
        </button>

        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          aria-label="Toggle color theme"
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/5 bg-slate-900/50 text-slate-400 hover:border-sky-400/30 hover:bg-slate-800/60 hover:text-white transition-all active:scale-95 cursor-pointer"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        {/* Analyzer Stats Panel toggle */}
        <button
          onClick={onTogglePanel}
          aria-label="Toggle analyzer panel"
          className={`flex h-9 w-9 items-center justify-center rounded-xl border transition-all active:scale-95 cursor-pointer ${
            panelOpen
              ? "border-sky-400/50 bg-sky-950/50 text-sky-300 shadow-[0_0_15px_rgba(56,189,248,0.2)]"
              : "border-white/5 bg-slate-900/50 text-slate-400 hover:border-sky-400/30 hover:bg-slate-800/60 hover:text-white"
          }`}
        >
          <BarChart3 className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
});
