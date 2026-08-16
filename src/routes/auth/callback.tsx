import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import type { User } from "@/lib/auth";

export const Route = createFileRoute("/auth/callback")({
  // CRIT-6: Tokens are now delivered via URL hash fragment (#) instead of query params (?).
  // Hash fragments are NOT sent to servers in HTTP requests, so tokens are
  // not logged in server access logs or captured by intermediate proxies.
  // We intentionally do NOT use validateSearch here — hash fragments are parsed manually
  // from window.location.hash, because routers don't expose hash params in search.
  validateSearch: () => ({}),
  head: () => ({ meta: [{ title: "Signing in… | SS Spark" }] }),
  component: AuthCallbackPage,
});

function AuthCallbackPage() {
  const navigate = useNavigate();
  const { setTokens, isAdmin } = useAuth();

  useEffect(() => {
    // Parse tokens from URL hash fragment (set by backend after OAuth)
    // Format: /auth/callback#access_token=XXX&refresh_token=YYY
    const hash = window.location.hash.substring(1); // Remove leading '#'
    const params = new URLSearchParams(hash);
    const access_token = params.get("access_token") ?? "";
    const refresh_token = params.get("refresh_token") ?? "";

    // Clear the hash from URL immediately (security hygiene)
    if (window.history?.replaceState) {
      window.history.replaceState(null, "", window.location.pathname);
    }

    if (!access_token || !refresh_token) {
      toast.error("Authentication failed. Please try again.");
      navigate({ to: "/login" });
      return;
    }

    // Store tokens and fetch user profile
    localStorage.setItem("pg_access_token", access_token);
    localStorage.setItem("pg_refresh_token", refresh_token);

    apiFetch<{ success: boolean; data: User }>("/api/auth/me", {
      headers: { Authorization: `Bearer ${access_token}` },
    })
      .then(({ data }) => {
        setTokens({ access_token, refresh_token }, data);
        toast.success(`Welcome, ${data.full_name || data.email}! 🎉`);
        if (data.role === "admin") {
          navigate({ to: "/admin" });
        } else {
          navigate({ to: "/" });
        }
      })
      .catch(() => {
        toast.error("Failed to fetch profile. Please try logging in again.");
        navigate({ to: "/login" });
      });
  }, [setTokens, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="flex justify-center mb-6">
          <div className="p-4 rounded-2xl animate-pulse gradient-brand shadow-lg">
            <Sparkles className="h-8 w-8 text-brand-foreground" />
          </div>
        </div>
        <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
        <h2 className="text-lg font-semibold" style={{ fontFamily: "var(--font-display)" }}>
          Completing sign in…
        </h2>
        <p className="text-sm text-muted-foreground mt-2">You'll be redirected in a moment.</p>
      </div>
    </div>
  );
}
