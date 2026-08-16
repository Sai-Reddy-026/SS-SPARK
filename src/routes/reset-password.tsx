import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate, useSearch } from "@tanstack/react-router";
import { toast } from "sonner";
import { CheckCircle, Eye, EyeOff, Loader2, Sparkles } from "lucide-react";
import { authApi } from "@/lib/api";

export const Route = createFileRoute("/reset-password")({
  validateSearch: (s) => ({ token: String((s as Record<string, unknown>).token ?? "") }),
  head: () => ({ meta: [{ title: "Reset Password | SS Spark" }] }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const navigate = useNavigate();
  const { token } = useSearch({ from: "/reset-password" });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!token) {
      toast.error("Invalid reset link");
      navigate({ to: "/forgot-password" });
    }
  }, [token, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!password) errs.password = "Password is required";
    else if (password.length < 8) errs.password = "Minimum 8 characters";
    if (password !== confirm) errs.confirm = "Passwords do not match";
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    setIsLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
      toast.success("Password reset successfully!");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Reset failed. Try requesting a new link.");
    } finally {
      setIsLoading(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-6">
        <div className="w-full max-w-md text-center">
          <div className="flex justify-center mb-4">
            <CheckCircle className="h-16 w-16 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Password updated!</h2>
          <p className="text-muted-foreground mb-6">Your password has been reset. You can now sign in with your new password.</p>
          <Link to="/login"
                className="inline-flex items-center justify-center rounded-xl px-6 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 hover-lift">
            Go to Sign In
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <div className="p-3 rounded-2xl gradient-brand shadow-lg">
            <Sparkles className="h-8 w-8 text-brand-foreground" />
          </div>
        </div>
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Set new password</h2>
          <p className="text-muted-foreground">Enter your new password below.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium mb-2">New Password</label>
            <div className="relative">
              <input
                id="new-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: "" })); }}
                placeholder="At least 8 characters"
                className="w-full rounded-xl border bg-card px-4 py-3 pr-10 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                style={{ borderColor: errors.password ? "var(--destructive)" : undefined }}
              />
              <button type="button" onClick={() => setShowPassword((p) => !p)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      aria-label="Toggle visibility">
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password && <p className="mt-1 text-xs text-destructive">{errors.password}</p>}
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium mb-2">Confirm Password</label>
            <input
              id="confirm-password"
              type="password"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setErrors((p) => ({ ...p, confirm: "" })); }}
              placeholder="Repeat your new password"
              className="w-full rounded-xl border bg-card px-4 py-3 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
              style={{ borderColor: errors.confirm ? "var(--destructive)" : undefined }}
            />
            {errors.confirm && <p className="mt-1 text-xs text-destructive">{errors.confirm}</p>}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift"
          >
            {isLoading ? <><Loader2 className="h-4 w-4 animate-spin" /> Resetting…</> : "Reset Password"}
          </button>
        </form>
      </div>
    </div>
  );
}
