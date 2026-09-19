import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: "surface" | "elevated" | "interactive" | "glow";
  className?: string;
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(function GlassCard(
  { children, variant = "surface", className = "", ...props },
  ref,
) {
  const baseStyles =
    "relative overflow-hidden rounded-2xl border transition-all duration-300 ease-out";

  const variantStyles = {
    surface:
      "bg-[rgba(9,15,30,0.65)] border-[rgba(255,255,255,0.07)] backdrop-blur-xl shadow-[0_16px_40px_-15px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.06)]",
    elevated:
      "bg-[rgba(12,20,38,0.78)] border-[rgba(56,189,248,0.15)] backdrop-blur-2xl shadow-[0_24px_60px_-18px_rgba(0,0,0,0.85),0_0_24px_-6px_rgba(56,189,248,0.1),inset_0_1px_0_rgba(255,255,255,0.08)]",
    interactive:
      "bg-[rgba(9,15,30,0.65)] border-[rgba(255,255,255,0.07)] backdrop-blur-xl shadow-[0_16px_40px_-15px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.06)] hover:border-[rgba(56,189,248,0.35)] hover:bg-[rgba(14,24,46,0.75)] hover:-translate-y-1 hover:shadow-[0_24px_50px_-12px_rgba(0,0,0,0.85),0_0_28px_-6px_rgba(56,189,248,0.2),inset_0_1px_0_rgba(255,255,255,0.12)] cursor-pointer",
    glow:
      "bg-[rgba(10,18,36,0.75)] border-[rgba(56,189,248,0.25)] backdrop-blur-2xl shadow-[0_24px_60px_-16px_rgba(0,0,0,0.8),0_0_36px_-6px_rgba(56,189,248,0.22),inset_0_1px_0_rgba(255,255,255,0.1)]",
  };

  return (
    <div
      ref={ref}
      className={cn(baseStyles, variantStyles[variant], className)}
      {...props}
    >
      {/* Subtle specular top highlight line */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 35%, rgba(56,189,248,0.3) 50%, rgba(255,255,255,0.15) 65%, transparent 100%)",
        }}
      />
      {children}
    </div>
  );
});
