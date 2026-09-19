import { useEffect, useState, useCallback } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import { Atmosphere, ParticleField, SparkCore, GlassCard } from "@/components/astra";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign In | SS Spark" },
      { name: "description", content: "Sign in to SS Spark — Astra-Powered AI Question Paper Workspace" },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { login, setGuest, isAuthenticated, isAdmin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [btnPulse, setBtnPulse] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0.5, y: 0.5 });

  // Mouse parallax tracking
  const handleMouseMove = useCallback((e: MouseEvent) => {
    setMousePos({
      x: e.clientX / window.innerWidth,
      y: e.clientY / window.innerHeight,
    });
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [handleMouseMove]);

  // Auth redirection
  useEffect(() => {
    if (isAuthenticated) {
      if (isAdmin) {
        navigate({ to: "/admin" });
      } else {
        navigate({ to: "/" });
      }
    }
  }, [isAuthenticated, isAdmin, navigate]);

  // OAuth error messages from backend redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("error");
    if (oauthError) {
      toast.error(decodeURIComponent(oauthError));
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  const validate = () => {
    const errs: { email?: string; password?: string } = {};
    if (!email.trim()) errs.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = "Enter a valid email";
    if (!password) errs.password = "Password is required";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setBtnPulse(true);
    setTimeout(() => setBtnPulse(false), 650);
    setIsLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back to SS Spark!");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuthClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (!res.ok) throw new Error("Backend unavailable");
      window.location.href = `${API_BASE}/api/auth/oauth/google`;
    } catch {
      toast.error(`Cannot connect to backend server at ${API_BASE}. Please ensure the FastAPI server is running.`);
    }
  };

  const handleGuest = () => {
    setGuest();
    toast("Browsing as guest — session context active.");
    navigate({ to: "/" });
  };

  const tiltX = (mousePos.y - 0.5) * -10;
  const tiltY = (mousePos.x - 0.5) * 14;

  return (
    <div className="relative min-h-screen w-full overflow-hidden flex flex-col items-center justify-center px-4 py-8">
      {/* ── Astra Cosmic Atmosphere & Particles ── */}
      <Atmosphere mouseX={mousePos.x} mouseY={mousePos.y} showGrid={true} intensity="full" />
      <ParticleField mouseX={mousePos.x} mouseY={mousePos.y} density="high" />

      {/* ── Top Header Brand ── */}
      <header className="absolute top-6 inset-x-0 flex items-center justify-between px-6 sm:px-12 z-20 pointer-events-none">
        <div className="flex items-center gap-3 pointer-events-auto">
          <SparkCore variant="compact" />
          <div>
            <span className="text-sm font-bold tracking-widest text-slate-200 uppercase font-mono">
              SS SPARK
            </span>
            <span className="ml-2.5 hidden sm:inline-block rounded-full border border-sky-400/25 bg-sky-950/40 px-2 py-0.5 text-[10px] font-mono text-sky-300">
              ASTRA CORE 2.5
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4 pointer-events-auto">
          <button
            onClick={handleGuest}
            className="text-xs font-mono text-slate-400 hover:text-sky-300 transition-colors py-1.5 px-3 rounded-lg border border-white/5 hover:border-sky-400/30 bg-slate-950/40 backdrop-blur-md"
          >
            Guest Access →
          </button>
        </div>
      </header>

      {/* ── Main Cinematic Grid: 3D Spark Core + Floating Login Console ── */}
      <div className="relative z-10 w-full max-w-5xl mx-auto flex flex-col lg:flex-row items-center justify-center gap-10 lg:gap-16 pt-12 lg:pt-0">
        {/* Left Column: SS Spark 3D Energy Object */}
        <div className="flex flex-col items-center text-center lg:text-left lg:items-start max-w-md">
          <div className="mb-4">
            <SparkCore mouseX={mousePos.x} mouseY={mousePos.y} variant="hero" showBadges={true} />
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white font-display">
            The Neural Workspace for <span className="gradient-text">Exam Mastery</span>
          </h1>
          <p className="mt-3 text-sm sm:text-base leading-relaxed text-slate-400 max-w-sm">
            Step-by-step solutions, mathematical formula precision, and answers verified strictly against your uploaded documents.
          </p>
        </div>

        {/* Right Column: Floating Astra Glass Login Console */}
        <div
          className="w-full max-w-md transition-transform duration-300 ease-out"
          style={{
            transform: `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`,
          }}
        >
          <GlassCard variant="elevated" className="p-7 sm:p-9">
            {/* Header */}
            <div className="mb-7">
              <div className="flex items-center gap-2 mb-2">
                <span className="h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_8px_#38bdf8] animate-pulse" />
                <span className="text-[11px] font-mono tracking-wider text-sky-400 uppercase">
                  Terminal Authentication
                </span>
              </div>
              <h2 className="text-xl font-bold tracking-tight text-white">
                Sign in to your account
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Enter your credentials to access your papers & AI solver
              </p>
            </div>

            {/* Google OAuth Button */}
            <a
              href={`${API_BASE}/api/auth/oauth/google`}
              onClick={handleOAuthClick}
              className="flex w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-slate-900/60 py-2.5 px-4 text-xs font-medium text-slate-200 transition-all duration-200 hover:border-sky-400/40 hover:bg-slate-800/60 hover:text-white"
            >
              <svg width="15" height="15" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
                />
                <path
                  fill="#34A853"
                  d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.36 24 12 24z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.28 14.27A7.2 7.2 0 0 1 4.9 12c0-.79.14-1.56.38-2.27V6.58H1.25A11.98 11.98 0 0 0 0 12c0 1.92.45 3.74 1.25 5.42l4.03-3.15z"
                />
                <path
                  fill="#EA4335"
                  d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.36 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                />
              </svg>
              Continue with Google
            </a>

            {/* Divider */}
            <div className="relative my-5 flex items-center">
              <div className="flex-grow border-t border-white/10" />
              <span className="mx-3 text-[10px] font-mono text-slate-500 uppercase tracking-widest">
                Or with Email
              </span>
              <div className="flex-grow border-t border-white/10" />
            </div>

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider mb-1.5">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setErrors((p) => ({ ...p, email: undefined }));
                  }}
                  placeholder="student@university.edu"
                  className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all duration-200"
                />
                {errors.email && (
                  <p className="text-[11px] text-rose-400 mt-1">{errors.email}</p>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider">
                    Password
                  </label>
                  <Link
                    to="/forgot-password"
                    className="text-[11px] text-sky-400/80 hover:text-sky-300 transition-colors"
                  >
                    Forgot?
                  </Link>
                </div>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setErrors((p) => ({ ...p, password: undefined }));
                    }}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2.5 pr-10 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all duration-200"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-[11px] text-rose-400 mt-1">{errors.password}</p>
                )}
              </div>

              {/* Submit Button */}
              <button
                id="login-submit-btn"
                type="submit"
                disabled={isLoading}
                className={`w-full py-3 rounded-xl border border-sky-400/40 bg-gradient-to-r from-sky-500/20 via-indigo-500/25 to-sky-500/20 text-sky-100 font-semibold text-sm tracking-wide transition-all duration-200 hover:border-sky-400/70 hover:shadow-[0_0_25px_rgba(56,189,248,0.25)] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${
                  btnPulse ? "scale-[1.02]" : ""
                }`}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin text-sky-300" />
                    Authenticating…
                  </>
                ) : (
                  <>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M13.8 12H3"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Enter Workspace
                  </>
                )}
              </button>
            </form>

            {/* Footer */}
            <div className="mt-6 pt-5 border-t border-white/5 flex flex-col items-center gap-3 text-center">
              <p className="text-xs text-slate-400">
                New to SS Spark?{" "}
                <Link
                  to="/register"
                  className="font-medium text-sky-400 hover:text-sky-300 transition-colors ml-1"
                >
                  Create free account →
                </Link>
              </p>
              <button
                onClick={handleGuest}
                className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
              >
                Explore features in Guest Mode
              </button>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}