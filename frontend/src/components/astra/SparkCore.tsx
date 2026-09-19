import { memo } from "react";

interface SparkCoreProps {
  variant?: "hero" | "compact" | "ambient";
  mouseX?: number;
  mouseY?: number;
  className?: string;
  showBadges?: boolean;
}

export const SparkCore = memo(function SparkCore({
  variant = "hero",
  mouseX = 0.5,
  mouseY = 0.5,
  className = "",
  showBadges = true,
}: SparkCoreProps) {
  // Parallax tilt angles
  const tiltX = (mouseY - 0.5) * -18;
  const tiltY = (mouseX - 0.5) * 22;

  if (variant === "compact") {
    return (
      <div
        className={`relative flex items-center justify-center ${className}`}
        style={{ width: 36, height: 36, perspective: 400 }}
        aria-hidden="true"
      >
        {/* Core glow */}
        <div
          className="absolute inset-0 rounded-full blur-md opacity-70 animate-pulse"
          style={{ background: "radial-gradient(circle, rgba(56,189,248,0.8) 0%, rgba(129,140,248,0.3) 70%, transparent 100%)" }}
        />
        {/* Orbital mini ring */}
        <div
          className="absolute inset-0 rounded-full border border-sky-400/50"
          style={{
            animation: "astra-orbit 8s linear infinite",
            transformStyle: "preserve-3d",
          }}
        />
        {/* Inner geometric core */}
        <div
          className="relative h-4 w-4 rounded-md border border-white/70 shadow-[0_0_12px_rgba(56,189,248,0.9)]"
          style={{
            background: "linear-gradient(135deg, rgba(56,189,248,0.9) 0%, rgba(99,102,241,0.9) 100%)",
            transform: "rotate(45deg)",
          }}
        />
      </div>
    );
  }

  const size = variant === "ambient" ? 180 : 280;

  return (
    <div
      className={`relative flex items-center justify-center select-none ${className}`}
      style={{
        width: size,
        height: size,
        perspective: 1200,
      }}
      aria-hidden="true"
    >
      <style>{`
        @keyframes astra-core-pulse {
          0%, 100% { transform: scale(1); opacity: 0.85; filter: blur(30px); }
          50% { transform: scale(1.15); opacity: 1; filter: blur(40px); }
        }
        @keyframes astra-facet-rotate {
          0% { transform: rotateY(0deg) rotateX(15deg); }
          50% { transform: rotateY(180deg) rotateX(-15deg); }
          100% { transform: rotateY(360deg) rotateX(15deg); }
        }
        @keyframes astra-facet-rotate-rev {
          0% { transform: rotateX(0deg) rotateY(-25deg); }
          50% { transform: rotateX(180deg) rotateY(25deg); }
          100% { transform: rotateX(360deg) rotateY(-25deg); }
        }
        @keyframes astra-ring-primary {
          0% { transform: rotate3d(1, 0.7, 0.3, 0deg); }
          100% { transform: rotate3d(1, 0.7, 0.3, 360deg); }
        }
        @keyframes astra-ring-secondary {
          0% { transform: rotate3d(-0.4, 1, 0.6, 0deg); }
          100% { transform: rotate3d(-0.4, 1, 0.6, -360deg); }
        }
        @keyframes astra-ring-equator {
          0% { transform: rotateX(80deg) rotateZ(0deg); }
          100% { transform: rotateX(80deg) rotateZ(360deg); }
        }
        @keyframes astra-float-node {
          0%, 100% { transform: translateY(0) scale(1); opacity: 0.6; }
          50% { transform: translateY(-10px) scale(1.2); opacity: 1; }
        }
      `}</style>

      {/* 3D Tilt Container */}
      <div
        className="relative flex items-center justify-center transition-transform duration-300 ease-out"
        style={{
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
          transform: `rotateX(${tiltX}deg) rotateY(${tiltY}deg)`,
        }}
      >
        {/* Core Volumetric Glow Bloom */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: size * 0.75,
            height: size * 0.75,
            background: "radial-gradient(circle, rgba(56,189,248,0.7) 0%, rgba(99,102,241,0.5) 45%, rgba(129,140,248,0.2) 70%, transparent 100%)",
            animation: "astra-core-pulse 5s ease-in-out infinite",
          }}
        />

        {/* Primary Orbital Energy Ring */}
        <div
          className="absolute rounded-full border border-sky-400/35"
          style={{
            width: size * 0.95,
            height: size * 0.95,
            transformStyle: "preserve-3d",
            animation: "astra-ring-primary 14s linear infinite",
            boxShadow: "0 0 20px rgba(56,189,248,0.2), inset 0 0 15px rgba(56,189,248,0.1)",
          }}
        >
          {/* Orbital Sparkle 1 */}
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 h-2.5 w-2.5 rounded-full bg-cyan-200 shadow-[0_0_12px_#38bdf8]"
          />
        </div>

        {/* Secondary Counter-Rotating Orbital Ring */}
        <div
          className="absolute rounded-full border border-indigo-400/30"
          style={{
            width: size * 0.85,
            height: size * 0.85,
            transformStyle: "preserve-3d",
            animation: "astra-ring-secondary 18s linear infinite",
            boxShadow: "0 0 18px rgba(99,102,241,0.2)",
          }}
        >
          {/* Orbital Sparkle 2 */}
          <div
            className="absolute bottom-0 right-1/4 h-2 w-2 rounded-full bg-violet-200 shadow-[0_0_10px_#818cf8]"
          />
        </div>

        {/* Equatorial Horizon Ring */}
        <div
          className="absolute rounded-full border border-sky-300/20"
          style={{
            width: size * 1.05,
            height: size * 1.05,
            transformStyle: "preserve-3d",
            animation: "astra-ring-equator 22s linear infinite",
          }}
        />

        {/* Outer 3D Geometric Prisms (Octahedral / Crystalline Structure) */}
        <div
          className="relative flex items-center justify-center"
          style={{
            width: size * 0.42,
            height: size * 0.42,
            transformStyle: "preserve-3d",
            animation: "astra-facet-rotate 16s ease-in-out infinite",
          }}
        >
          {/* Facet Layer 1 (Rotated Square Crystal) */}
          <div
            className="absolute inset-0 rounded-2xl border border-sky-300/60"
            style={{
              background: "linear-gradient(135deg, rgba(56,189,248,0.3) 0%, rgba(99,102,241,0.15) 100%)",
              backdropFilter: "blur(4px)",
              transform: "rotate(45deg)",
              boxShadow: "0 0 25px rgba(56,189,248,0.4), inset 0 1px 0 rgba(255,255,255,0.4)",
            }}
          />

          {/* Facet Layer 2 (Opposite Axis) */}
          <div
            className="absolute inset-0 rounded-2xl border border-violet-400/50"
            style={{
              background: "linear-gradient(225deg, rgba(129,140,248,0.3) 0%, rgba(56,189,248,0.15) 100%)",
              backdropFilter: "blur(4px)",
              transform: "rotate(45deg) rotateX(60deg)",
              boxShadow: "0 0 20px rgba(129,140,248,0.35)",
            }}
          />

          {/* Inner Light Singularity */}
          <div
            className="relative h-6 w-6 rounded-full bg-white shadow-[0_0_35px_#38bdf8,0_0_60px_#818cf8]"
            style={{
              animation: "astra-core-pulse 3s ease-in-out infinite",
            }}
          />
        </div>

        {/* Floating Holographic Telemetry Badges (for Hero Variant) */}
        {showBadges && variant === "hero" && (
          <>
            <div
              className="absolute -top-3 right-0 rounded-full border border-sky-400/25 bg-slate-950/80 px-3 py-1 backdrop-blur-md"
              style={{
                boxShadow: "0 4px 16px rgba(0,0,0,0.6), 0 0 12px rgba(56,189,248,0.15)",
                animation: "astra-float-node 5s ease-in-out infinite",
              }}
            >
              <div className="flex items-center gap-1.5 text-[10px] font-mono tracking-widest text-sky-300 uppercase">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 shadow-[0_0_6px_#38bdf8]" />
                Neural Grounding · Active
              </div>
            </div>

            <div
              className="absolute -bottom-4 left-0 rounded-full border border-violet-400/25 bg-slate-950/80 px-3 py-1 backdrop-blur-md"
              style={{
                boxShadow: "0 4px 16px rgba(0,0,0,0.6), 0 0 12px rgba(129,140,248,0.15)",
                animation: "astra-float-node 6s ease-in-out infinite 1.5s",
              }}
            >
              <div className="flex items-center gap-1.5 text-[10px] font-mono tracking-widest text-indigo-300 uppercase">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 shadow-[0_0_6px_#818cf8]" />
                SS Spark Engine · v2.5
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
});
