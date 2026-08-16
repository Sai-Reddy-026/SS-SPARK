/**
 * src/lib/api.ts
 *
 * Typed API client that automatically attaches Authorization headers,
 * handles token refresh, and provides typed wrappers for all backend endpoints.
 */

import { getStoredAccessToken, getStoredRefreshToken, isTokenExpired, clearStoredAuth, setStoredTokens } from "./auth";

// -------------------------------------------------------------------------- //
// Base fetcher
// -------------------------------------------------------------------------- //

export const API_BASE = (import.meta.env.VITE_API_URL as string) || "http://localhost:8000";

type FetchOptions = RequestInit & {
  skipAuth?: boolean;
};

async function _getValidToken(): Promise<string | null> {
  const access = getStoredAccessToken();
  if (!access) return null;

  if (!isTokenExpired(access)) return access;

  // Try to refresh
  const refresh = getStoredRefreshToken();
  if (!refresh) {
    clearStoredAuth();
    return null;
  }

  try {
    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (response.ok) {
      const data = await response.json();
      const newAccess: string = data.data.access_token;
      setStoredTokens(newAccess, refresh);
      return newAccess;
    }
  } catch {
    // Silent
  }

  clearStoredAuth();
  return null;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { skipAuth = false, headers = {}, ...rest } = options;
  const authHeaders: Record<string, string> = {};

  if (!skipAuth) {
    const token = await _getValidToken();
    if (token) {
      authHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
        ...(headers as Record<string, string>),
      },
    });
  } catch (netErr: unknown) {
    throw new Error(
      `Cannot connect to backend server at ${API_BASE}. Please ensure the FastAPI server is running.`
    );
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      (errorData as { detail?: string; message?: string }).detail ??
      (errorData as { detail?: string; message?: string }).message ??
      `HTTP ${response.status}`;
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData,
): Promise<T> {
  const token = await _getValidToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      (errorData as { detail?: string; message?: string }).detail ??
      (errorData as { detail?: string; message?: string }).message ??
      `HTTP ${response.status}`;
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

// -------------------------------------------------------------------------- //
// Auth API
// -------------------------------------------------------------------------- //

export const authApi = {
  forgotPassword: (email: string) =>
    apiFetch("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
      skipAuth: true,
    }),

  resetPassword: (token: string, newPassword: string) =>
    apiFetch("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
      skipAuth: true,
    }),

  verifyEmail: (token: string) =>
    apiFetch("/api/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
      skipAuth: true,
    }),

  updateProfile: (data: { full_name?: string; avatar_url?: string }) =>
    apiFetch("/api/auth/me", { method: "PATCH", body: JSON.stringify(data) }),
};

// -------------------------------------------------------------------------- //
// Documents API
// -------------------------------------------------------------------------- //

export const documentsApi = {
  list: () =>
    apiFetch<{ success: boolean; data: DocumentResponse[] }>("/api/documents"),

  delete: (docId: string) =>
    apiFetch(`/api/documents/${docId}`, { method: "DELETE" }),

  rename: (docId: string, name: string) =>
    apiFetch(`/api/documents/${docId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return apiUpload<{ success: boolean; data: UploadResponse[] }>("/api/upload", form);
  },
};

// -------------------------------------------------------------------------- //
// Chat API
// -------------------------------------------------------------------------- //

export const chatApi = {
  send: (question: string, sessionId?: string) =>
    apiFetch<ChatApiResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ question, session_id: sessionId }),
    }),

  history: (sessionId: string, limit?: number) =>
    apiFetch<{ success: boolean; data: MessageResponse[] }>(
      `/api/history?session_id=${sessionId}${limit ? `&limit=${limit}` : ""}`,
    ),
};

// -------------------------------------------------------------------------- //
// Sessions API
// -------------------------------------------------------------------------- //

export const sessionsApi = {
  list: () => apiFetch<{ success: boolean; data: SessionResponse[] }>("/api/sessions"),

  create: (title?: string) =>
    apiFetch<{ success: boolean; data: SessionResponse }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title: title ?? "New Chat" }),
    }),

  update: (id: string, updates: Partial<SessionResponse>) =>
    apiFetch<{ success: boolean; data: SessionResponse }>(`/api/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  delete: (id: string) =>
    apiFetch(`/api/sessions/${id}`, { method: "DELETE" }),
};

// -------------------------------------------------------------------------- //
// Analytics API
// -------------------------------------------------------------------------- //

export const analyticsApi = {
  userStats: () =>
    apiFetch<{ success: boolean; data: UserStats }>("/api/analytics/user"),

  activity: (days?: number) =>
    apiFetch<{ success: boolean; data: ActivityDay[] }>(
      `/api/analytics/activity${days ? `?days=${days}` : ""}`,
    ),

  panelStats: () =>
    apiFetch<{ success: boolean; data: PanelStats }>("/api/analytics/panel"),
};

// -------------------------------------------------------------------------- //
// Notifications API
// -------------------------------------------------------------------------- //

export const notificationsApi = {
  list: () =>
    apiFetch<{ success: boolean; data: NotificationItem[] }>("/api/notifications"),
  markRead: () =>
    apiFetch("/api/notifications/read", { method: "POST" }),
};

// -------------------------------------------------------------------------- //
// Response types
// -------------------------------------------------------------------------- //

export interface DocumentResponse {
  id: string;
  name: string;
  kind: string;
  size_mb: number;
  pages: number;
  chunk_count: number;
  uploaded_at: string;
  user_id?: string;
}

export interface UploadResponse {
  id: string;
  name?: string;
  filename: string;
  kind: string;
  size_mb: number;
  pages: number;
  chunk_count?: number;
  chunks_indexed: number;
  paperqa_indexed: boolean;
  uploaded_at: string;
  message: string;
}

export interface CitationResponse {
  id: string;
  source: string;
  page: number;
  snippet: string;
  relevance: number;
}

export interface ChatApiResponse {
  success: boolean;
  data: {
    answer: string;
    source: string;
    page: number;
    confidence: number;
    citations: CitationResponse[];
    references: string;
    session_id: string;
    cost: number;
    status: string;
  };
  message: string;
}

export interface MessageResponse {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  confidence?: number;
  citations: CitationResponse[];
}

export interface SessionResponse {
  id: string;
  user_id: string;
  title: string;
  pinned: boolean;
  archived: boolean;
  folder: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface UserStats {
  questions_asked: number;
  documents_uploaded: number;
  storage_used_mb: number;
  average_confidence: number;
  sessions_count: number;
}

export interface ActivityDay {
  date: string;
  questions: number;
  uploads: number;
}

export interface PanelStats {
  total_documents: number;
  total_questions: number;
  topic_data: { topic: string; count: number }[];
  subject_data: { name: string; value: number }[];
  year_data: { year: string; papers: number }[];
  recent_questions: { q: string; years: string }[];
}

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  kind: string;
  read: boolean;
  created_at: string;
}
