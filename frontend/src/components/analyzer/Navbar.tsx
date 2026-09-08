import { BarChart3, Menu, Moon, Sun, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface NavbarProps {
  onToggleSidebar: () => void;
  onTogglePanel: () => void;
  panelOpen: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  docCount: number;
  onOpenSearchPad?: () => void;
}

export function Navbar({
  onToggleSidebar,
  onTogglePanel,
  panelOpen,
  theme,
  onToggleTheme,
  docCount,
  onOpenSearchPad,
}: NavbarProps) {
  return (
    <header className="relative grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 bg-background/50 px-3 py-2.5 backdrop-blur-xl sm:px-5">
      {/* Gradient bottom border */}
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      <div className="flex min-w-0 items-center gap-2.5">
        <Button variant="ghost" size="icon" onClick={onToggleSidebar} aria-label="Toggle sidebar" className="shrink-0">
          <Menu className="h-4 w-4" />
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold tracking-tight">
            <span className="gradient-text">AI Question Paper Analyzer</span>
          </p>
          <p className="hidden truncate text-[11px] text-muted-foreground/70 sm:block">
            Grounded answers from your own documents
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          onClick={onOpenSearchPad}
          title="Open Document Search Pad"
          className="hidden sm:inline-flex"
        >
          <Badge variant="secondary" className="gap-1.5 cursor-pointer transition-all hover:bg-accent hover-glow">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-chart-2 opacity-40" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-chart-2" />
            </span>
            {docCount} source{docCount === 1 ? "" : "s"}
          </Badge>
        </button>
        <Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label="Toggle color theme" className="transition-transform hover:scale-105 active:scale-95">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Button
          variant={panelOpen ? "secondary" : "ghost"}
          size="icon"
          onClick={onTogglePanel}
          aria-label="Toggle analyzer panel"
          className="transition-transform hover:scale-105 active:scale-95"
        >
          <BarChart3 className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}

