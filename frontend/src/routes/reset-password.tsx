import { useState, useMemo } from "react";
import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { authApi } from "@/lib/api";

export const Route = createFileRoute("/reset-password")({
  validateSearch: (s) => ({
    token: String((s as Record<string, unknown>).token ?? ""),
  }),
  head: () => ({ meta: [{ title: "Reset Password | SS SPARK" }] }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const { token } = useSearch({ from: "/reset-password" });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isTokenInvalid, setIsTokenInvalid] = useState(!token);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Password strength checks
  const strength = useMemo(() => {
    const hasMinLen = password.length >= 8;
    const hasNum = /\d/.test(password);
    const hasSpecial = /[^A-Za-z0-9]/.test(password);
    const score = [hasMinLen, hasNum, hasSpecial, password.length >= 12].filter(Boolean).length;
    return { hasMinLen, hasNum, hasSpecial, score };
  }, [password]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setIsTokenInvalid(true);
      return;
    }

    const errs: Record<string, string> = {};
    if (!password) {
      errs.password = "Please enter a new password";
    } else if (password.length < 8) {
      errs.password = "Password must be at least 8 characters long";
    }

    if (!confirm) {
      errs.confirm = "Please confirm your new password";
    } else if (password !== confirm) {
      errs.confirm = "Passwords do not match";
    }

    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setIsLoading(true);
    setErrorMessage("");
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
      toast.success("Password has been reset successfully!");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Password reset failed";
      setErrorMessage(msg);
      // If the error indicates expired or invalid token
      if (
        msg.toLowerCase().includes("invalid") ||
        msg.toLowerCase().includes("expired") ||
        msg.toLowerCase().includes("used")
      ) {
        setIsTokenInvalid(true);
      }
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // ─── 1. Success State ───
  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 py-12">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-border/60 bg-card/60 p-6 sm:p-8 shadow-xl backdrop-blur-sm text-center animate-message-in">
            <div className="flex justify-center mb-4">
              <div
                className="p-4 rounded-full"
                style={{
                  background: "oklch(0.72 0.16 158 / 15%)",
                  border: "1px solid oklch(0.72 0.16 158 / 30%)",
                }}
              >
                <CheckCircle className="h-10 w-10 text-emerald-400" />
              </div>
            </div>
            <h2 className="text-2xl font-bold mb-2">Password Updated!</h2>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              Your password has been successfully reset. All previous sessions have been logged out for security.
            </p>
            <Link
              to="/login"
              className="w-full inline-flex items-center justify-center rounded-xl px-6 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 hover-lift"
            >
              Sign In with New Password
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ─── 2. Invalid or Expired Token State ───
  if (isTokenInvalid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 py-12">
        <div className="w-full max-w-md">
          <div className="flex justify-center mb-8">
            <div className="p-3.5 rounded-2xl gradient-brand shadow-lg">
              <Sparkles className="h-8 w-8 text-brand-foreground" />
            </div>
          </div>

          <div className="rounded-2xl border border-destructive/40 bg-card/60 p-6 sm:p-8 shadow-xl backdrop-blur-sm text-center animate-message-in">
            <div className="flex justify-center mb-4">
              <div className="p-4 rounded-full bg-destructive/10 border border-destructive/30">
                <AlertTriangle className="h-10 w-10 text-destructive" />
              </div>
            </div>
            <h2 className="text-2xl font-bold mb-2">Reset link invalid or expired</h2>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              {errorMessage ||
                "This password reset link is invalid, has expired (after 30 minutes), or has already been used."}
            </p>

            <div className="space-y-3">
              <Link
                to="/forgot-password"
                className="w-full flex items-center justify-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 hover-lift"
              >
                <RefreshCw className="h-4 w-4" />
                Request a New Reset Link
              </Link>
              <Link
                to="/login"
                className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl border border-border bg-background/80 px-4 py-2.5 text-sm font-medium text-foreground hover:bg-accent transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Sign In
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── 3. Set New Password Form ───
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <div className="p-3.5 rounded-2xl gradient-brand shadow-lg">
            <Sparkles className="h-8 w-8 text-brand-foreground" />
          </div>
        </div>

        <div className="rounded-2xl border border-border/60 bg-card/60 p-6 sm:p-8 shadow-xl backdrop-blur-sm">
          <div className="text-center mb-6">
            <h2 className="text-2xl sm:text-3xl font-bold mb-2">Set new password</h2>
            <p className="text-sm text-muted-foreground">
              Choose a strong password with at least 8 characters.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* New Password */}
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium mb-1.5">
                New Password
              </label>
              <div className="relative">
                <input
                  id="new-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setErrors((p) => ({ ...p, password: "" }));
                  }}
                  placeholder="At least 8 characters"
                  className="w-full rounded-xl border bg-background/60 px-4 py-2.5 pr-10 text-sm outline-none transition-all focus:ring-2 focus:ring-primary placeholder:text-muted-foreground/60"
                  style={{ borderColor: errors.password ? "var(--destructive)" : undefined }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="mt-1.5 text-xs text-destructive">{errors.password}</p>}

              {/* Password strength checklist */}
              {password && (
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                  <span
                    className={`inline-flex items-center gap-1 ${
                      strength.hasMinLen ? "text-emerald-400" : ""
                    }`}
                  >
                    <Check className="h-3 w-3" /> 8+ characters
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 ${
                      strength.hasNum ? "text-emerald-400" : ""
                    }`}
                  >
                    <Check className="h-3 w-3" /> Includes number
                  </span>
                </div>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirm-password" className="block text-sm font-medium mb-1.5">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="confirm-password"
                  type={showConfirm ? "text" : "password"}
                  value={confirm}
                  onChange={(e) => {
                    setConfirm(e.target.value);
                    setErrors((p) => ({ ...p, confirm: "" }));
                  }}
                  placeholder="Repeat your new password"
                  className="w-full rounded-xl border bg-background/60 px-4 py-2.5 pr-10 text-sm outline-none transition-all focus:ring-2 focus:ring-primary placeholder:text-muted-foreground/60"
                  style={{ borderColor: errors.confirm ? "var(--destructive)" : undefined }}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Toggle confirm password visibility"
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirm && <p className="mt-1.5 text-xs text-destructive">{errors.confirm}</p>}
            </div>

            {errorMessage && !isTokenInvalid && (
              <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/30 text-xs text-destructive">
                {errorMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Updating Password…
                </>
              ) : (
                <>
                  <Lock className="h-4 w-4" />
                  Reset Password
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Remember your password?{" "}
            <Link to="/login" className="text-primary font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
