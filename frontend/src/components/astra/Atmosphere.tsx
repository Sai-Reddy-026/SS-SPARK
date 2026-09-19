import { memo } from "react";

interface AtmosphereProps {
  mouseX?: number;
  mouseY?: number;
  showGrid?: boolean;
  intensity?: "full" | "subtle" | "ambient";
}

export const Atmosphere = memo(function Atmosphere({
  mouseX = 0.5,
  mouseY = 0.5,
  showGrid = true,
  intensity = "full",
}: AtmosphereProps) {
  // Parallax displacement based on mouse coordinates (-15px to +15px)
  const shiftX = (mouseX - 0.5) * 30;
  const shiftY = (mouseY - 0.5) * 24;

  const opacityMult = intensity === "subtle" ? 0.6 : intensity === "ambient" ? 0.4 : 1;

  return (
    <div
      className="pointer-events-none fixed inset-0 -z-50 overflow-hidden select-none"
      style={{ background: "#030509" }}
      aria-hidden="true"
    >
      {/* Deep celestial gradient mesh */}
      <div
        className="absolute inset-0 transition-transform duration-700 ease-out"
        style={{
          transform: `translate3d(${shiftX * 0.4}px, ${shiftY * 0.4}px, 0)`,
          background: `
            radial-gradient(circle at ${20 + mouseX * 20}% ${25 + mouseY * 20}%, rgba(56, 189, 248, ${0.12 * opacityMult}) 0%, transparent 60%),
            radial-gradient(circle at ${78 - mouseX * 15}% ${70 - mouseY * 15}%, rgba(99, 102, 241, ${0.11 * opacityMult}) 0%, transparent 65%),
            radial-gradient(circle at 50% 50%, rgba(129, 140, 248, ${0.05 * opacityMult}) 0%, transparent 70%)
          `,
        }}
      />

      {/* Volumetric cyan ambient spotlight */}
      <div
        className="absolute rounded-full blur-[140px] transition-transform duration-1000 ease-out"
        style={{
          width: "55vw",
          height: "45vh",
          top: "10%",
          left: "15%",
          background: `radial-gradient(circle, rgba(56, 189, 248, ${0.09 * opacityMult}) 0%, transparent 70%)`,
          transform: `translate3d(${shiftX * 0.8}px, ${shiftY * 0.8}px, 0)`,
        }}
      />

      {/* Volumetric violet counter-light */}
      <div
        className="absolute rounded-full blur-[160px] transition-transform duration-1000 ease-out"
        style={{
          width: "50vw",
          height: "50vh",
          bottom: "5%",
          right: "10%",
          background: `radial-gradient(circle, rgba(129, 140, 248, ${0.08 * opacityMult}) 0%, transparent 70%)`,
          transform: `translate3d(${-shiftX * 0.6}px, ${-shiftY * 0.6}px, 0)`,
        }}
      />

      {/* Receding 3D perspective grid plane */}
      {showGrid && (
        <div
          className="absolute inset-x-0 bottom-0 h-[48vh] opacity-[0.14] transition-transform duration-500 ease-out"
          style={{
            transform: `perspective(1000px) rotateX(68deg) translate3d(${shiftX * 0.2}px, 0, 0)`,
            transformOrigin: "bottom center",
            backgroundImage: `
              linear-gradient(to right, rgba(56, 189, 248, 0.35) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(56, 189, 248, 0.35) 1px, transparent 1px)
            `,
            backgroundSize: "64px 64px",
            maskImage: "linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.8) 40%, rgba(0,0,0,1) 100%)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.8) 40%, rgba(0,0,0,1) 100%)",
          }}
        />
      )}

      {/* Soft horizon glow line */}
      <div
        className="absolute inset-x-0 bottom-[40vh] h-[1px] opacity-25"
        style={{
          background: "linear-gradient(90deg, transparent 0%, rgba(56, 189, 248, 0.5) 50%, transparent 100%)",
          boxShadow: "0 0 30px 2px rgba(56, 189, 248, 0.3)",
        }}
      />

      {/* Vignette / depth-of-field edge darkening */}
      <div
        className="absolute inset-0"
        style={{
          background: "radial-gradient(circle at 50% 50%, transparent 55%, rgba(3, 5, 9, 0.8) 100%)",
        }}
      />
    </div>
  );
});
