export type DocKind = "pdf" | "docx" | "txt" | "image";

export interface UploadedDoc {
  id: string;
  name: string;
  kind: DocKind;
  typeLabel: string;
  uploadedAt: Date;
  pages: number;
  previewUrl?: string | undefined;
  questionsCount?: number;
}

export interface Citation {
  id: string;
  source: string;
  page: number;
  snippet: string;
  relevance: number;
}

export interface ChatAttachment {
  name: string;
  type: string;
  size: number;
  previewUrl?: string;
  dataUrl?: string;
}

export interface ChatMessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: Date;
  confidence?: number;
  citations?: Citation[];
  /** "success" | "partial" | "unsure" | "general" | "error" — set by the backend */
  status?: string;
  /** True while the assistant message is still streaming tokens */
  isStreaming?: boolean;
  /** Attached image or document for this message */
  attachment?: ChatAttachment;
}

export function kindFromName(name: string): DocKind {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["png", "jpg", "jpeg", "webp"].includes(ext)) return "image";
  if (ext === "docx" || ext === "doc") return "docx";
  if (ext === "txt") return "txt";
  return "pdf";
}

export function typeLabel(kind: DocKind) {
  return {
    pdf: "PDF Document",
    docx: "Word Document",
    txt: "Text File",
    image: "Question Paper Image",
  }[kind];
}

export function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
