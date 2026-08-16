import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate, useSearch } from "@tanstack/react-router";
import { CheckCircle, Loader2, Sparkles, XCircle } from "lucide-react";
import { authApi } from "@/lib/api";

export const Route = createFileRoute("/verify-email")({
  validateSearch: (s) => ({ token: String((s as Record<string, unknown>).token ?? "") }),
  head: () => ({ meta: [{ title: "Verify Email | SS Spark" }] }),
  component: VerifyEmailPage,
});

function VerifyEmailPage() {
  const { token } = useSearch({ from: "/verify-email" });
  const navigate = useNavigate();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token found in the link.");
      return;
    }

    authApi
      .verifyEmail(token)
      .then(() => {
        setStatus("success");
        setMessage("Your email has been verified successfully!");
        setTimeout(() => navigate({ to: "/" }), 3000);
      })
      .catch((err: unknown) => {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Verification failed. The link may be expired.");
      });
  }, [token, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6">
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center mb-6">
          <div className="p-3 rounded-2xl mb-2 gradient-brand shadow-lg">
            <Sparkles className="h-8 w-8 text-brand-foreground" />
          </div>
        </div>

        {status === "loading" && (
          <>
            <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Verifying your email…</h2>
            <p className="text-muted-foreground">Please wait a moment.</p>
          </>
        )}

        {status === "success" && (
          <>
            <CheckCircle className="h-16 w-16 text-emerald-400 mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Email verified!</h2>
            <p className="text-muted-foreground mb-6">{message}</p>
            <p className="text-sm text-muted-foreground">Redirecting to your dashboard…</p>
            <Link to="/" className="mt-4 inline-flex items-center gap-2 text-primary text-sm hover:underline">
              Go to dashboard now →
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <XCircle className="h-16 w-16 text-destructive mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-display)" }}>Verification failed</h2>
            <p className="text-muted-foreground mb-6">{message}</p>
            <div className="flex flex-col gap-3 items-center">
              <Link to="/login"
                    className="inline-flex items-center justify-center rounded-xl px-6 py-3 text-sm font-semibold gradient-brand text-brand-foreground shadow-lg shadow-orange-950/30 hover-lift">
                Go to Sign In
              </Link>
              <p className="text-xs text-muted-foreground">
                Need a new link? Sign in and request verification from your profile.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
