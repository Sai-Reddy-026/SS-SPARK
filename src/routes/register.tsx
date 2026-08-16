import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2, Sparkles, UserPlus } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create Account | SS Spark" },
      { name: "description", content: "Create your free SS Spark account" },
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

  useEffect(() => {
    if (isAuthenticated) {
      navigate({ to: "/" });
    }
  }, [isAuthenticated, navigate]);

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
    <div className="min-h-screen flex bg-background">
      {/* Decorative left */}
      <div className="hidden lg:flex lg:w-1/2 relative items-center justify-center overflow-hidden bg-[#0a0a0c] border-r border-border/40">
        <div className="absolute inset-0 opacity-25"
             style={{ backgroundImage: "radial-gradient(circle at 60% 40%, oklch(0.76 0.19 60) 0%, transparent 55%), radial-gradient(circle at 30% 70%, oklch(0.68 0.22 45) 0%, transparent 45%)" }} />
        <div className="relative z-10 max-w-md px-12 text-center">
          <div className="mb-8 flex justify-center">
            <div className="p-4 rounded-2xl gradient-brand shadow-lg">
              <Sparkles className="h-12 w-12 text-brand-foreground" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-white mb-4" style={{ fontFamily: "var(--font-display)" }}>
            Join SS Spark
          </h1>
          <p className="text-lg text-white/70 leading-relaxed mb-8">
            Start analyzing question papers with AI in minutes. Free to get started.
          </p>
          <div className="space-y-3 text-left">
            {[
              "Upload unlimited documents",
              "AI answers grounded in your papers",
              "Full citation with page numbers",
              "Generate flashcards and quizzes",
              "Export answers to PDF & DOCX",
            ].map((f) => (
              <div key={f} className="flex items-center gap-3">
                <div className="h-5 w-5 rounded-full flex items-center justify-center flex-shrink-0"
                     style={{ background: "oklch(0.72 0.16 158 / 30%)", border: "1px solid oklch(0.72 0.16 158 / 50%)" }}>
                  <svg viewBox="0 0 12 12" className="h-3 w-3 text-emerald-400" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="2,6 5,9 10,3" />
                  </svg>
                </div>
                <span className="text-sm text-white/80">{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex justify-center mb-8">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl gradient-brand">
                <Sparkles className="h-6 w-6 text-brand-foreground" />
              </div>
              <span className="text-xl font-bold" style={{ fontFamily: "var(--font-display)" }}>SS Spark</span>
            </div>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold" style={{ fontFamily: "var(--font-display)" }}>Create account</h2>
            <p className="text-muted-foreground mt-2">Get started with SS Spark for free</p>
          </div>

          {/* OAuth */}
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
              Sign up with Google
            </a>
          </div>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-background px-4 text-xs text-muted-foreground">or register with email</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {[
              { id: "name", label: "Full Name", type: "text", placeholder: "Your name", key: "name" },
              { id: "email", label: "Email", type: "email", placeholder: "you@example.com", key: "email" },
            ].map(({ id, label, type, placeholder, key }) => (
              <div key={id}>
                <label htmlFor={id} className="block text-sm font-medium mb-2">{label}</label>
                <input
                  id={id}
                  type={type}
                  value={form[key as keyof typeof form]}
                  onChange={(e) => set(key, e.target.value)}
                  placeholder={placeholder}
                  className="w-full rounded-xl border bg-card px-4 py-3 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                  style={{ borderColor: errors[key] ? "var(--destructive)" : undefined }}
                />
                {errors[key] && <p className="mt-1 text-xs text-destructive">{errors[key]}</p>}
              </div>
            ))}

            {/* Password */}
            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium mb-2">Password</label>
              <div className="relative">
                <input
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={(e) => set("password", e.target.value)}
                  placeholder="At least 8 characters"
                  className="w-full rounded-xl border bg-card px-4 py-3 pr-10 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                  style={{ borderColor: errors.password ? "var(--destructive)" : undefined }}
                />
                <button type="button" onClick={() => setShowPassword((p) => !p)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        aria-label="Toggle password">
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-destructive">{errors.password}</p>}
            </div>

            <div>
              <label htmlFor="confirm" className="block text-sm font-medium mb-2">Confirm Password</label>
              <input
                id="confirm"
                type="password"
                value={form.confirm}
                onChange={(e) => set("confirm", e.target.value)}
                placeholder="Repeat your password"
                className="w-full rounded-xl border bg-card px-4 py-3 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                style={{ borderColor: errors.confirm ? "var(--destructive)" : undefined }}
              />
              {errors.confirm && <p className="mt-1 text-xs text-destructive">{errors.confirm}</p>}
            </div>

            <button
              id="register-submit-btn"
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift"
            >
              {isLoading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Creating account…</>
              ) : (
                <><UserPlus className="h-4 w-4" /> Create Account</>
              )}
            </button>

            <p className="text-xs text-center text-muted-foreground">
              By signing up you agree to our Terms of Service and Privacy Policy.
            </p>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
