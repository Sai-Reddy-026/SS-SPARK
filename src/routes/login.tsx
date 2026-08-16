import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2, LogIn, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign In | SS Spark" },
      { name: "description", content: "Sign in to SS Spark — AI Question Paper Analyzer" },
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

  // Redirect if already logged in
  useEffect(() => {
    if (isAuthenticated) {
      if (isAdmin) {
        navigate({ to: "/admin" });
      } else {
        navigate({ to: "/" });
      }
    }
  }, [isAuthenticated, isAdmin, navigate]);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    if (!email) newErrors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) newErrors.email = "Enter a valid email";
    if (!password) newErrors.password = "Password is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setIsLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back!");
      // navigate happens via isAuthenticated check above
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuthClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      const targetUrl = `${API_BASE}/api/auth/oauth/google`;
      const res = await fetch(targetUrl, { redirect: "manual" });
      if (res.status === 501) {
        const data = await res.json().catch(() => ({}));
        toast.error(data.detail || "Google OAuth is not configured in backend .env");
        return;
      }
      window.location.href = targetUrl;
    } catch {
      toast.error(`Cannot connect to backend server at ${API_BASE}. Please ensure the FastAPI server is running.`);
    }
  };

  const handleGuest = () => {
    setGuest();
    toast("Browsing as guest — uploads and chats won't be saved.");
    navigate({ to: "/" });
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Left decorative panel */}
      <div className="hidden lg:flex lg:w-1/2 relative items-center justify-center overflow-hidden bg-[#0a0a0c] border-r border-border/40">
        <div className="absolute inset-0 opacity-25"
             style={{ backgroundImage: "radial-gradient(circle at 30% 50%, oklch(0.68 0.22 45) 0%, transparent 60%), radial-gradient(circle at 70% 20%, oklch(0.76 0.19 60) 0%, transparent 40%)" }} />
        <div className="relative z-10 max-w-md px-12 text-center">
          <div className="mb-8 flex justify-center">
            <div className="p-4 rounded-2xl gradient-brand shadow-lg">
              <Sparkles className="h-12 w-12 text-brand-foreground" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-white mb-4" style={{ fontFamily: "var(--font-display)" }}>
            SS Spark
          </h1>
          <p className="text-lg text-white/70 leading-relaxed mb-8">
            AI-powered question paper analyzer. Upload papers, notes, and textbooks — ask questions and get cited answers instantly.
          </p>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Documents", value: "∞" },
              { label: "Accuracy", value: "94%" },
              { label: "Speed", value: "<2s" },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl p-4 text-center border border-white/10 bg-white/5 backdrop-blur-sm">
                <div className="text-2xl font-bold text-white">{value}</div>
                <div className="text-xs text-white/60 mt-1">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Logo (mobile only) */}
          <div className="lg:hidden flex justify-center mb-8">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl gradient-brand">
                <Sparkles className="h-6 w-6 text-brand-foreground" />
              </div>
              <span className="text-xl font-bold" style={{ fontFamily: "var(--font-display)" }}>
                SS Spark
              </span>
            </div>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold" style={{ fontFamily: "var(--font-display)" }}>
              Welcome back
            </h2>
            <p className="text-muted-foreground mt-2">Sign in to continue to your workspace</p>
          </div>

          {/* OAuth button */}
          <div className="mb-6">
            <a href={`${API_BASE}/api/auth/oauth/google`}
               onClick={(e) => handleOAuthClick(e)}
               className="flex w-full items-center justify-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium transition-all hover:bg-accent hover-lift">
              <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </a>
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-background px-4 text-xs text-muted-foreground">or continue with email</span>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: undefined })); }}
                placeholder="you@example.com"
                className="w-full rounded-xl border bg-card px-4 py-3 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                style={{ borderColor: errors.email ? "var(--destructive)" : undefined }}
              />
              {errors.email && <p className="mt-1 text-xs text-destructive">{errors.email}</p>}
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label htmlFor="password" className="block text-sm font-medium">Password</label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">Forgot password?</Link>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }}
                  placeholder="••••••••"
                  className="w-full rounded-xl border bg-card px-4 py-3 pr-10 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                  style={{ borderColor: errors.password ? "var(--destructive)" : undefined }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-destructive">{errors.password}</p>}
            </div>

            <button
              id="login-submit-btn"
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift"
            >
              {isLoading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Signing in…</>
              ) : (
                <><LogIn className="h-4 w-4" /> Sign In</>
              )}
            </button>
          </form>

          {/* Footer links */}
          <div className="mt-6 space-y-3 text-center text-sm text-muted-foreground">
            <p>
              Don't have an account?{" "}
              <Link to="/register" className="text-primary font-medium hover:underline">
                Create account
              </Link>
            </p>
            <button
              onClick={handleGuest}
              className="text-xs hover:text-foreground transition-colors"
            >
              Continue as guest →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
