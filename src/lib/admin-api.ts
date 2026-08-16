/**
 * src/lib/admin-api.ts
 * Typed API client for all admin-only endpoints.
 */

import { apiFetch } from "./api";

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string;
  role: "user" | "admin";
  status: string;
  email_verified: boolean;
  provider: string;
  total_documents: number;
  total_questions: number;
  storage_used_mb: number;
  created_at: string;
  last_login: string | null;
}

export interface AdminDocument {
  id: string;
  name: string;
  kind: string;
  size_mb: number;
  pages: number;
  user_id: string;
  chunk_count: number;
  uploaded_at: string;
}

export interface GlobalStats {
  total_users: number;
  active_users: number;
  total_sessions: number;
  total_documents: number;
  total_questions: number;
  total_storage_mb: number;
  new_users_last_7_days: number;
}

export interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  detail: string;
  ip_address: string | null;
  created_at: string;
}

export interface SystemHealth {
  mongodb: { status: string; database?: string; error?: string };
  chromadb: { status: string; chunk_count?: number; error?: string };
  paperqa: { status: string; indexed_documents: number };
  server: { python: string; platform: string };
}

export interface SystemSettings {
  ocr_engine: string;
  embedding_model: string;
  llm_model: string;
  chunk_size: number;
  chunk_overlap: number;
  max_upload_size_mb: number;
  allowed_file_types: string[];
  rate_limit_requests_per_minute: number;
  maintenance_mode: boolean;
  updated_at: string;
}

export const adminApi = {
  // Users
  getUsers: (params?: { skip?: number; limit?: number; search?: string; role?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.search) qs.set("search", params.search);
    if (params?.role) qs.set("role", params.role);
    if (params?.status) qs.set("status", params.status);
    return apiFetch<{ success: boolean; data: AdminUser[]; total: number }>(
      `/api/admin/users?${qs.toString()}`
    );
  },

  getUser: (id: string) =>
    apiFetch<{ success: boolean; data: AdminUser }>(`/api/admin/users/${id}`),

  editUser: (id: string, updates: Partial<AdminUser>) =>
    apiFetch(`/api/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(updates) }),

  deleteUser: (id: string) =>
    apiFetch(`/api/admin/users/${id}`, { method: "DELETE" }),

  suspendUser: (id: string) =>
    apiFetch(`/api/admin/users/${id}/suspend`, { method: "POST" }),

  activateUser: (id: string) =>
    apiFetch(`/api/admin/users/${id}/activate`, { method: "POST" }),

  changeRole: (id: string, role: "user" | "admin") =>
    apiFetch(`/api/admin/users/${id}/role`, { method: "POST", body: JSON.stringify({ role }) }),

  // Documents
  getDocuments: (params?: { skip?: number; limit?: number; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.search) qs.set("search", params.search);
    return apiFetch<{ success: boolean; data: AdminDocument[]; total: number }>(
      `/api/admin/documents?${qs.toString()}`
    );
  },

  deleteDocument: (id: string) =>
    apiFetch(`/api/admin/documents/${id}`, { method: "DELETE" }),

  reindexDocument: (id: string) =>
    apiFetch(`/api/admin/documents/${id}/reindex`, { method: "POST" }),

  // Analytics
  getStats: () =>
    apiFetch<{ success: boolean; data: GlobalStats }>("/api/admin/analytics"),

  getActivity: (days?: number) =>
    apiFetch<{ success: boolean; data: Array<{ date: string; questions: number; uploads: number }> }>(
      `/api/admin/analytics/activity${days ? `?days=${days}` : ""}`
    ),

  // System
  getSystemHealth: () =>
    apiFetch<{ success: boolean; data: SystemHealth }>("/api/admin/system"),

  // Logs
  getLogs: (params?: { user_id?: string; action?: string; skip?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.user_id) qs.set("user_id", params.user_id);
    if (params?.action) qs.set("action", params.action);
    if (params?.skip) qs.set("skip", String(params.skip));
    if (params?.limit) qs.set("limit", String(params.limit));
    return apiFetch<{ success: boolean; data: AuditLog[]; total: number }>(
      `/api/admin/logs?${qs.toString()}`
    );
  },

  // Settings
  getSettings: () =>
    apiFetch<{ success: boolean; data: SystemSettings }>("/api/admin/settings"),

  updateSettings: (updates: Partial<SystemSettings>) =>
    apiFetch("/api/admin/settings", { method: "PATCH", body: JSON.stringify(updates) }),

  // Notifications
  sendNotification: (payload: { title: string; body: string; kind?: string; user_id?: string }) =>
    apiFetch("/api/admin/notifications", { method: "POST", body: JSON.stringify(payload) }),
};
