import { useState, useEffect, useRef } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, Loader2, Mail, RefreshCw, Sparkles } from "lucide-react";
import { authApi } from "@/lib/api";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({
    meta: [{ title: "Forgot Password | SS SPARK" }],
  }),
  component: ForgotPasswordPage,
});

const RESEND_COOLDOWN_SECONDS = 60;

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [error, setError] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldown > 0) {
      timerRef.current = setInterval(() => {
        setCooldown((prev) => {
          if (prev <= 1) {
            if (timerRef.current) clearInterval(timerRef.current);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [cooldown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError("Please enter your email address");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      setError("Please enter a valid email address");
      return;
    }

    setIsLoading(true);
    setError("");
    try {
      await authApi.forgotPassword(cleanEmail);
      setSent(true);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      toast.success("Password reset request submitted");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      toast.error(msg);
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (cooldown > 0 || isResending) return;
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) return;

    setIsResending(true);
    try {
      await authApi.resendResetLink(cleanEmail);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      toast.success("New reset link sent! Check your inbox.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to resend link";
      toast.error(msg);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 py-12">
      <div className="w-full max-w-md">
        {/* Brand Icon */}
        <div className="flex justify-center mb-8">
          <div className="p-3.5 rounded-2xl gradient-brand shadow-lg">
            <Sparkles className="h-8 w-8 text-brand-foreground" />
          </div>
        </div>

        {sent ? (
          /* ── Confirmation / Resend View ── */
          <div className="rounded-2xl border border-border/60 bg-card/60 p-6 sm:p-8 shadow-xl backdrop-blur-sm text-center animate-message-in">
            <div className="flex justify-center mb-5">
              <div
                className="p-4 rounded-full"
                style={{
                  background: "oklch(0.72 0.16 158 / 15%)",
                  border: "1px solid oklch(0.72 0.16 158 / 30%)",
                }}
              >
                <Mail className="h-8 w-8 text-emerald-400" />
              </div>
            </div>

            <h2 className="text-2xl font-bold mb-2">Check your email</h2>
            <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
              If an account exists for <strong className="text-foreground font-medium">{email}</strong>, we have sent a password reset link to your inbox.
            </p>

            <div className="rounded-xl border border-border/40 bg-accent/40 px-4 py-3 text-xs text-muted-foreground text-left mb-6 space-y-1">
              <p className="font-medium text-foreground flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                Next steps:
              </p>
              <p>1. Open the reset email in your inbox (Gmail, Outlook, Yahoo, etc.).</p>
              <p>2. Check your <strong>Spam or Junk</strong> folder if you don't see it within 2 minutes.</p>
              <p>3. The link will safely expire in <strong>30 minutes</strong>.</p>
            </div>

            {/* Resend Action */}
            <div className="border-t border-border/50 pt-5 space-y-3">
              <p className="text-xs text-muted-foreground">
                Didn't receive the email?
              </p>

              <button
                type="button"
                onClick={handleResend}
                disabled={cooldown > 0 || isResending}
                className="w-full flex items-center justify-center gap-2 rounded-xl border border-border bg-background/80 px-4 py-2.5 text-sm font-medium text-foreground transition-all hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isResending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Sending new link…
                  </>
                ) : cooldown > 0 ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 opacity-50" />
                    Resend available in {cooldown}s
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 text-primary" />
                    Send a new reset link
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setSent(false);
                  setCooldown(0);
                  setError("");
                }}
                className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
              >
                Use a different email address
              </button>
            </div>

            <div className="mt-6 pt-4 border-t border-border/40">
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                <ArrowLeft className="h-4 w-4" /> Back to sign in
              </Link>
            </div>
          </div>
        ) : (
          /* ── Initial Form View ── */
          <div className="rounded-2xl border border-border/60 bg-card/60 p-6 sm:p-8 shadow-xl backdrop-blur-sm">
            <div className="text-center mb-6">
              <h2 className="text-2xl sm:text-3xl font-bold mb-2">Forgot password?</h2>
              <p className="text-sm text-muted-foreground">
                Enter your registered email address and we'll send you a secure password reset link.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="forgot-email" className="block text-sm font-medium mb-1.5">
                  Email address
                </label>
                <input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError("");
                  }}
                  placeholder="name@example.com"
                  className="w-full rounded-xl border bg-background/60 px-4 py-2.5 text-sm outline-none transition-all focus:ring-2 focus:ring-primary placeholder:text-muted-foreground/60"
                  style={{ borderColor: error ? "var(--destructive)" : undefined }}
                />
                {error && <p className="mt-1.5 text-xs text-destructive">{error}</p>}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Sending reset link…
                  </>
                ) : (
                  <>
                    <Mail className="h-4 w-4" /> Send Reset Link
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
        )}
      </div>
    </div>
  );
}
