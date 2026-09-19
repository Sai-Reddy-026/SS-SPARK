import { useState, useEffect, useRef } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, Loader2, Mail, RefreshCw } from "lucide-react";
import { authApi } from "@/lib/api";
import { Atmosphere, SparkCore, GlassCard } from "@/components/astra";

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
    <div className="relative min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 py-12 overflow-hidden">
      <Atmosphere showGrid={false} intensity="subtle" />

      <div className="w-full max-w-md relative z-10">
        {/* Brand Icon */}
        <div className="flex justify-center mb-6">
          <SparkCore variant="compact" />
        </div>

        {sent ? (
          /* ── Confirmation / Resend View ── */
          <GlassCard variant="elevated" className="p-7 sm:p-9 text-center animate-message-in">
            <div className="flex justify-center mb-4">
              <div className="p-3.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <Mail className="h-7 w-7" />
              </div>
            </div>

            <h2 className="text-xl font-bold mb-2 tracking-tight text-white">Check your email</h2>
            <p className="text-xs text-slate-400 mb-4 leading-relaxed">
              If an account exists for <strong className="text-slate-200">{email}</strong>, we have sent a password reset link to your inbox.
            </p>

            <div className="rounded-xl border border-white/5 bg-slate-950/40 px-4 py-3 text-xs text-slate-400 text-left mb-5 space-y-1">
              <p className="font-semibold text-slate-200 flex items-center gap-1.5 text-[11px] font-mono uppercase">
                <CheckCircle2 className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                Instructions:
              </p>
              <p>1. Open the reset link in your email.</p>
              <p>2. Check your Spam or Junk folder if delayed.</p>
              <p>3. Link expires in 30 minutes.</p>
            </div>

            {/* Resend Action */}
            <div className="border-t border-white/5 pt-4 space-y-2.5">
              <button
                type="button"
                onClick={handleResend}
                disabled={cooldown > 0 || isResending}
                className="w-full flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-slate-900/60 px-4 py-2 text-xs font-medium text-slate-200 hover:border-sky-400/40 disabled:opacity-50 cursor-pointer"
              >
                {isResending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Sending link…
                  </>
                ) : cooldown > 0 ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 opacity-50" />
                    Resend in {cooldown}s
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 text-sky-400" />
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
                className="text-xs text-slate-400 hover:text-sky-300 transition-colors cursor-pointer"
              >
                Use a different email address
              </button>
            </div>

            <div className="mt-5 pt-4 border-t border-white/5">
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-sky-400 hover:text-sky-300"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
              </Link>
            </div>
          </GlassCard>
        ) : (
          /* ── Initial Form View ── */
          <GlassCard variant="elevated" className="p-7 sm:p-9">
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold tracking-tight text-white mb-1.5">Reset your password</h2>
              <p className="text-xs text-slate-400">
                Enter your registered email address to receive a secure recovery link.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="forgot-email" className="block text-[11px] font-mono text-slate-300 uppercase tracking-wider mb-1">
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
                  placeholder="student@university.edu"
                  className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-sky-400/60 focus:ring-1 focus:ring-sky-400/30 transition-all"
                />
                {error && <p className="mt-1 text-[11px] text-rose-400">{error}</p>}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 rounded-xl border border-sky-400/40 bg-gradient-to-r from-sky-500/20 via-indigo-500/25 to-sky-500/20 text-sky-100 font-semibold text-sm tracking-wide transition-all duration-200 hover:border-sky-400/70 hover:shadow-[0_0_20px_rgba(56,189,248,0.2)] active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-2 cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-sky-300" /> Sending reset link…
                  </>
                ) : (
                  <>
                    <Mail className="h-4 w-4" /> Send Reset Link
                  </>
                )}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-slate-400">
              Remember your password?{" "}
              <Link to="/login" className="text-sky-400 hover:text-sky-300 font-medium">
                Sign in →
              </Link>
            </p>
          </GlassCard>
        )}
      </div>
    </div>
  );
}
