import { useEffect, useState, useCallback } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Check, Eye, EyeOff, Loader2, UserPlus } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import { Atmosphere, ParticleField, SparkCore, GlassCard } from "@/components/astra";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create Account | SS Spark" },
      { name: "description", content: "Create your free SS Spark account — Astra-Powered AI Question Paper Analyzer" },
    ],
  }),
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const { register, isAuthenticated } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [mousePos, setMousePos] = useState({ x: 0.5, y: 0.5 });

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

  useEffect(() => {
    if (isAuthenticated) {
      navigate({ to: "/" });
    }
  }, [isAuthenticated, navigate]);

  // Show OAuth error messages passed back from backend redirect (?error=...)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("error");
    if (oauthError) {
      toast.error(decodeURIComponent(oauthError));
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  const handleOAuthClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error("Backend unavailable");
      window.location.href = `${API_BASE}/api/auth/oauth/google`;
    } catch {
      toast.error(`Cannot connect to backend at ${API_BASE}. Please make sure the FastAPI server is running.`);
    }
  };

  const set = (key: string, value: string) => {
    setForm((p) => ({ ...p, [key]: value }));
    setErrors((p) => ({ ...p, [key]: "" }));
  };

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = "Full name is required";
    if (!form.email) errs.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = "Enter a valid email";
    if (!form.password) errs.password = "Password is required";
    else if (form.password.length < 8) errs.password = "Password must be at least 8 characters";
    if (form.password !== form.confirm) errs.confirm = "Passwords do not match";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setIsLoading(true);
    try {
      await register(form.email, form.password, form.name);
      toast.success("Account created! Welcome to SS Spark 🎉");
      navigate({ to: "/" });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden flex flex-col items-center justify-center px-4 py-8">
      {/* ── Astra Cosmic Atmosphere & Particles ── */}
      <Atmosphere mouseX={mousePos.x} mouseY={mousePos.y} showGrid={true} intensity="full" />
      <ParticleField mouseX={mousePos.x} mouseY={mousePos.y} density="medium" />

      {/* ── Top Header Brand ── */}
      <header className="absolute top-6 inset-x-0 flex items-center justify-between px-6 sm:px-12 z-20 pointer-events-none">
        <Link to="/" className="flex items-center gap-3 pointer-events-auto">
          <SparkCore variant="compact" />
          <span className="text-sm font-bold tracking-widest text-slate-200 uppercase font-mono">
            SS SPARK
          </span>
        </Link>
        <Link
          to="/login"
          className="pointer-events-auto text-xs font-mono text-slate-400 hover:text-sky-300 transition-colors py-1.5 px-3 rounded-lg border border-white/5 hover:border-sky-400/30 bg-slate-950/40 backdrop-blur-md"
        >
          Sign in →
        </Link>
      </header>

      {/* ── Center Container ── */}
      <div className="relative z-10 w-full max-w-5xl mx-auto flex flex-col lg:flex-row items-center justify-center gap-10 lg:gap-14 pt-14 lg:pt-0">
        {/* Left Side: Astra Perks & Core */}
        <div className="flex flex-col items-center text-center lg:text-left lg:items-start max-w-md">
          <div className="mb-2">
            <SparkCore mouseX={mousePos.x} mouseY={mousePos.y} variant="ambient" showBadges={false} />
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white font-display">
            Join the <span className="gradient-text">SS Spark Universe</span>
          </h1>
          <p className="mt-2 text-sm text-slate-400 leading-relaxed max-w-sm">
            Instant paper analysis, handwritten exam OCR, step-by-step math solver, and grounded citations.
          </p>

          {/* Features check list */}
          <div className="mt-6 space-y-2.5 w-full max-w-sm text-left">
            {[
              "Unlimited question paper & textbook analysis",
              "100% document-grounded answers with citations",
              "Mathematical formula & code precision",
              "Topic repetition & recurring questions tracker",
            ].map((text) => (
              <div
                key={text}
                className="flex items-center gap-3 rounded-xl border border-white/5 bg-slate-950/30 px-3 py-2 backdrop-blur-sm"
              >
                <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 border border-sky-400/30">
                  <Check className="h-3 w-3" />
                </div>
                <span className="text-xs text-slate-300">{text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Side: Registration Console */}
        <div className="w-full max-w-md">
          <GlassCard variant="elevated" className="p-7 sm:p-9">
            <div className="mb-6">
              <h2 className="text-xl font-bold tracking-tight text-white">Create your account</h2>
              <p className="text-xs text-slate-400 mt-1">
                Enter your details to generate your workspace credentials
              </p>
            </div>

            {/* OAuth Google button */}
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
              Sign up with Google
            </a>

            <div className="relative my-4 flex items-center">
              <div className="flex-grow border-t border-white/10" />
              <span className="mx-3 text-[10px] font-mono text-slate-500 uppercase tracking-widest">
                Or with Email
              </span>
              <div className="flex-grow border-t border-white/10" />
            </div>

            <form onSubmit={handleSubmit} className="space-y-3.5" noValidate>
              <div>
                <label className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider mb-1">
                  Full Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                  placeholder="Alex Mercer"
                  className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all"
                />
                {errors.name && <p className="text-[11px] text-rose-400 mt-1">{errors.name}</p>}
              </div>

              <div>
                <label className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider mb-1">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  placeholder="student@university.edu"
                  className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all"
                />
                {errors.email && <p className="text-[11px] text-rose-400 mt-1">{errors.email}</p>}
              </div>

              <div>
                <label className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider mb-1">
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={form.password}
                    onChange={(e) => set("password", e.target.value)}
                    placeholder="At least 8 characters"
                    className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2 pr-10 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((p) => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  >
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-[11px] text-rose-400 mt-1">{errors.password}</p>
                )}
              </div>

              <div>
                <label className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider mb-1">
                  Confirm Password
                </label>
                <input
                  id="confirm"
                  type="password"
                  value={form.confirm}
                  onChange={(e) => set("confirm", e.target.value)}
                  placeholder="Repeat your password"
                  className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all"
                />
                {errors.confirm && (
                  <p className="text-[11px] text-rose-400 mt-1">{errors.confirm}</p>
                )}
              </div>

              <button
                id="register-submit-btn"
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 rounded-xl border border-sky-400/40 bg-gradient-to-r from-sky-500/20 via-indigo-500/25 to-sky-500/20 text-sky-100 font-semibold text-sm tracking-wide transition-all duration-200 hover:border-sky-400/70 hover:shadow-[0_0_20px_rgba(56,189,248,0.2)] active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-2 mt-2 cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin text-sky-300" />
                    Creating account…
                  </>
                ) : (
                  <>
                    <UserPlus size={15} />
                    Create Account
                  </>
                )}
              </button>
            </form>

            <p className="mt-5 text-center text-xs text-slate-400">
              Already have an account?{" "}
              <Link to="/login" className="text-sky-400 hover:text-sky-300 font-medium">
                Sign in →
              </Link>
            </p>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
