import { useEffect, useRef, memo } from "react";

interface ParticleFieldProps {
  mouseX?: number;
  mouseY?: number;
  density?: "high" | "medium" | "low";
}

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  alpha: number;
  baseAlpha: number;
  hue: number;
  life: number;
  maxLife: number;
};

export const ParticleField = memo(function ParticleField({
  mouseX = 0.5,
  mouseY = 0.5,
  density = "medium",
}: ParticleFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef({ x: mouseX, y: mouseY });

  useEffect(() => {
    mouseRef.current = { x: mouseX, y: mouseY };
  }, [mouseX, mouseY]);

  useEffect(() => {
    // Check reduced motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    // Calculate count based on viewport area and density
    const area = window.innerWidth * window.innerHeight;
    const baseCount = density === "high" ? 120 : density === "medium" ? 85 : 45;
    const count = Math.min(baseCount, Math.max(25, Math.floor(area / 18000)));

    particlesRef.current = Array.from({ length: count }, () => {
      const baseAlpha = Math.random() * 0.45 + 0.15;
      return {
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.2,
        vy: (Math.random() - 0.5) * 0.2 - 0.08,
        size: Math.random() * 1.6 + 0.4,
        alpha: baseAlpha,
        baseAlpha,
        hue: Math.random() < 0.65 ? 198 + Math.random() * 30 : 255 + Math.random() * 30, // Cyan & Soft Violet
        life: Math.random() * 350,
        maxLife: 250 + Math.random() * 350,
      };
    });

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const mx = mouseRef.current.x * canvas.width;
      const my = mouseRef.current.y * canvas.height;

      particlesRef.current.forEach((p) => {
        p.life++;
        if (p.life > p.maxLife) {
          p.x = Math.random() * canvas.width;
          p.y = canvas.height + 10;
          p.life = 0;
          p.maxLife = 250 + Math.random() * 350;
          p.vx = (Math.random() - 0.5) * 0.2;
          p.vy = -Math.random() * 0.3 - 0.06;
        }

        // Mouse gentle attraction
        const dx = mx - p.x;
        const dy = my - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 200 && dist > 0) {
          p.vx += (dx / dist) * 0.0035;
          p.vy += (dy / dist) * 0.0035;
        }

        // Damping
        p.vx *= 0.992;
        p.vy *= 0.992;
        p.x += p.vx;
        p.y += p.vy;

        // Wrap edges horizontally
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;

        // Alpha lifecycle fade in and out
        const progress = p.life / p.maxLife;
        const currentAlpha =
          progress < 0.2
            ? p.baseAlpha * (progress / 0.2)
            : progress > 0.8
            ? p.baseAlpha * ((1 - progress) / 0.2)
            : p.baseAlpha;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 90%, 75%, ${currentAlpha})`;
        ctx.shadowColor = `hsla(${p.hue}, 95%, 70%, 0.6)`;
        ctx.shadowBlur = p.size * 3;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [density]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 -z-40 h-full w-full"
      aria-hidden="true"
    />
  );
});
