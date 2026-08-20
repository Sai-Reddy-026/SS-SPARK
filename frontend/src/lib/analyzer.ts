export type DocKind = "pdf" | "docx" | "txt" | "image";

export interface UploadedDoc {
  id: string;
  name: string;
  kind: DocKind;
  typeLabel: string;
  uploadedAt: Date;
  pages: number;
  previewUrl?: string | undefined;
}

export interface Citation {
  id: string;
  source: string;
  page: number;
  snippet: string;
  relevance: number;
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
}


export interface ChatThread {
  id: string;
  title: string;
  subtitle: string;
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

export const recentChats: ChatThread[] = [
  { id: "c1", title: "DBMS 2023 repeated questions", subtitle: "12 questions analyzed" },
  { id: "c2", title: "Operating Systems unit 3 notes", subtitle: "Deadlock summary" },
  { id: "c3", title: "Maths-II probability trends", subtitle: "5 year comparison" },
  { id: "c4", title: "Compiler design important topics", subtitle: "Topic weightage" },
];

export const sampleAnswer = `Based on the uploaded papers, **normalization** appears in every year from 2020–2024.

### Why it repeats
1. It links theory with practical schema design.
2. Examiners can scale difficulty using dependency questions.

\`\`\`sql
-- Typical 3NF check asked in 2023 paper
SELECT student_id, course_id
FROM enrollment
GROUP BY student_id, course_id;
\`\`\`

Expect a *10-mark* question on converting a relation from 2NF to 3NF.`;

export const sampleCitations: Citation[] = [
  {
    id: "s1",
    source: "DBMS_2023_QuestionPaper.pdf",
    page: 2,
    snippet:
      "Q4 (a) Explain 2NF and 3NF with a suitable example. (b) Normalize the given relation up to 3NF. [10 marks]",
    relevance: 0.94,
  },
  {
    id: "s2",
    source: "DBMS_Unit2_Notes.pdf",
    page: 17,
    snippet:
      "A relation is in 3NF if it is in 2NF and no non-prime attribute is transitively dependent on the primary key.",
    relevance: 0.87,
  },
];

export const seedMessages: ChatMessageData[] = [
  {
    id: "m1",
    role: "user",
    content: "Which topics repeat the most in the DBMS question papers I uploaded?",
    createdAt: new Date(Date.now() - 1000 * 60 * 8),
  },
  {
    id: "m2",
    role: "assistant",
    content: sampleAnswer,
    createdAt: new Date(Date.now() - 1000 * 60 * 7),
    confidence: 0.92,
    citations: sampleCitations,
  },
];

export const seedDocs: UploadedDoc[] = [
  {
    id: "d1",
    name: "DBMS_2023_QuestionPaper.pdf",
    kind: "pdf",
    typeLabel: typeLabel("pdf"),
    uploadedAt: new Date(Date.now() - 1000 * 60 * 42),
    pages: 8,
  },
  {
    id: "d2",
    name: "DBMS_Unit2_Notes.pdf",
    kind: "pdf",
    typeLabel: typeLabel("pdf"),
    uploadedAt: new Date(Date.now() - 1000 * 60 * 30),
    pages: 24,
  },
  {
    id: "d3",
    name: "Handwritten_Paper_2022.jpg",
    kind: "image",
    typeLabel: typeLabel("image"),
    uploadedAt: new Date(Date.now() - 1000 * 60 * 12),
    pages: 1,
  },
];

export const topicData = [
  { topic: "Normalization", count: 18 },
  { topic: "Transactions", count: 14 },
  { topic: "Indexing", count: 11 },
  { topic: "SQL Joins", count: 9 },
  { topic: "ER Model", count: 7 },
];

export const subjectData = [
  { name: "DBMS", value: 38 },
  { name: "OS", value: 24 },
  { name: "Maths-II", value: 21 },
  { name: "Compilers", value: 17 },
];

export const yearData = [
  { year: "2020", papers: 3 },
  { year: "2021", papers: 4 },
  { year: "2022", papers: 6 },
  { year: "2023", papers: 7 },
  { year: "2024", papers: 5 },
];

export const repeatedQuestions = [
  { q: "Normalize the given relation up to 3NF.", years: "2020, 2022, 2023" },
  { q: "Explain ACID properties with examples.", years: "2021, 2023, 2024" },
  { q: "Compare clustered and non-clustered indexes.", years: "2022, 2024" },
];
