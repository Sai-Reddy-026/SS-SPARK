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
}

export function Navbar({
  onToggleSidebar,
  onTogglePanel,
  panelOpen,
  theme,
  onToggleTheme,
  docCount,
}: NavbarProps) {
  return (
    <header className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b bg-background/60 px-3 py-2.5 backdrop-blur-xl sm:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onToggleSidebar} aria-label="Toggle sidebar">
          <Menu className="h-4 w-4" />
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">AI Question Paper Analyzer</p>
          <p className="hidden truncate text-xs text-muted-foreground sm:block">
            Grounded answers from your own documents
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Badge variant="secondary" className="hidden gap-1 sm:flex">
          <Sparkles className="h-3 w-3 text-chart-2" />
          {docCount} sources
        </Badge>
        <Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label="Toggle color theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Button
          variant={panelOpen ? "secondary" : "ghost"}
          size="icon"
          onClick={onTogglePanel}
          aria-label="Toggle analyzer panel"
        >
          <BarChart3 className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
