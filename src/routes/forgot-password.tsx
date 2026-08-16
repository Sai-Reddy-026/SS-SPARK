import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Mail, Sparkles } from "lucide-react";
import { authApi } from "@/lib/api";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({
    meta: [{ title: "Forgot Password | SS Spark" }],
  }),
  component: ForgotPasswordPage,
});

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { setError("Please enter your email"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Enter a valid email"); return; }

    setIsLoading(true);
    setError("");
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <div className="p-3 rounded-2xl gradient-brand shadow-lg">
            <Sparkles className="h-8 w-8 text-brand-foreground" />
          </div>
        </div>

        {sent ? (
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <div className="p-4 rounded-full"
                   style={{ background: "oklch(0.72 0.16 158 / 15%)", border: "1px solid oklch(0.72 0.16 158 / 30%)" }}>
                <Mail className="h-8 w-8 text-emerald-400" />
              </div>
            </div>
            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Check your inbox</h2>
            <p className="text-muted-foreground mb-6">
              If an account exists for <strong>{email}</strong>, we've sent a password reset link. Check your spam folder too.
            </p>
            <Link to="/login"
                  className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
              <ArrowLeft className="h-4 w-4" /> Back to login
            </Link>
          </div>
        ) : (
          <>
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Forgot password?</h2>
              <p className="text-muted-foreground">Enter your email and we'll send you a reset link.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="forgot-email" className="block text-sm font-medium mb-2">Email address</label>
                <input
                  id="forgot-email"
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(""); }}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border bg-card px-4 py-3 text-sm outline-none transition-all focus:ring-2 focus:ring-primary"
                  style={{ borderColor: error ? "var(--destructive)" : undefined }}
                />
                {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 transition-all disabled:opacity-60 hover-lift"
              >
                {isLoading ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending…</> : <><Mail className="h-4 w-4" /> Send Reset Link</>}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Remember your password?{" "}
              <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
