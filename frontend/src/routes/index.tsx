import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AnalyzerSidebar, type SidebarChat } from "@/components/analyzer/AnalyzerSidebar";
import { UserSettingsModal } from "@/components/analyzer/UserSettingsModal";
import { Navbar } from "@/components/analyzer/Navbar";
import { ChatMessage, TypingIndicator } from "@/components/analyzer/ChatMessage";
import { ChatComposer } from "@/components/analyzer/ChatComposer";
import { AnalyzerPanel } from "@/components/analyzer/AnalyzerPanel";
import { UploadCard, ImagePreviewCard } from "@/components/analyzer/UploadCard";
import { UploadDropzone } from "@/components/analyzer/UploadDropzone";
import {
  kindFromName,
  sampleAnswer,
  sampleCitations,
  typeLabel,
  type ChatMessageData,
  type UploadedDoc,
} from "@/lib/analyzer";
import { useAuth } from "@/lib/auth";
import { chatApi, documentsApi, sessionsApi, type SessionResponse } from "@/lib/api";
import { BrainCircuit, FileText, Sparkles } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AI Question Paper Analyzer | SS SPARK" },
      {
        name: "description",
        content:
          "Upload previous question papers, notes and textbooks, then ask questions and get AI answers grounded only in your documents.",
      },
      { property: "og:title", content: "AI Question Paper Analyzer | SS SPARK" },
      {
        property: "og:description",
        content:
          "A premium AI workspace for analyzing question papers, notes and textbooks with cited, document-grounded answers.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AnalyzerPage,
});

// Suggested prompts shown on the empty state (ChatGPT style)
const SUGGESTED_PROMPTS = [
  "Which topics repeat most across all papers?",
  "Explain binary search with an example.",
  "What are the most important questions for the exam?",
  "Write a C++ program to implement BFS.",
];

function AnalyzerPage() {
  const { user, isGuest, isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [panelOpen, setPanelOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [docsLoading, setDocsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [activeChat, setActiveChat] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Track blob URLs for cleanup to prevent memory leaks
  const blobUrlsRef = useRef<Set<string>>(new Set());

  // Redirect to login if not authenticated and not guest (after auth loads)
  useEffect(() => {
    if (!authLoading && !isAuthenticated && !isGuest) {
      navigate({ to: "/login" });
    }
  }, [authLoading, isAuthenticated, isGuest, navigate]);

  // Load real documents from backend on mount (authenticated users only)
  useEffect(() => {
    if (!isAuthenticated) return;

    async function loadDocs() {
      setDocsLoading(true);
      try {
        const result = await documentsApi.list();
        const serverDocs: UploadedDoc[] = result.data.map((doc) => ({
          id: doc.id,
          name: doc.name,
          kind: kindFromName(doc.name),
          typeLabel: typeLabel(kindFromName(doc.name)),
          uploadedAt: new Date(doc.uploaded_at),
          pages: doc.pages,
          previewUrl: undefined,
        }));
        setDocs(serverDocs);
      } catch (err) {
        console.warn("Could not load documents:", err);
      } finally {
        setDocsLoading(false);
      }
    }

    loadDocs();
  }, [isAuthenticated]);

  // Fetch real chat sessions from backend
  const loadSessions = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const res = await sessionsApi.list();
      setSessions(res.data);
    } catch (err) {
      console.warn("Could not load chat sessions:", err);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("light", theme === "light");
    root.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    });
  }, [messages, loading]);

  // Cleanup blob URLs on unmount
  useEffect(() => {
    const currentBlobUrls = blobUrlsRef.current;
    return () => {
      currentBlobUrls.forEach((url) => URL.revokeObjectURL(url));
      currentBlobUrls.clear();
    };
  }, []);

  const imageDocs = useMemo(() => docs.filter((doc) => doc.kind === "image"), [docs]);
  const fileDocs = useMemo(() => docs.filter((doc) => doc.kind !== "image"), [docs]);

  // Convert SessionResponse to SidebarChat
  const sidebarChats = useMemo<SidebarChat[]>(() => {
    return sessions.map((s) => ({
      id: s.id,
      title: s.title || "New Chat",
      subtitle: `${s.message_count || 0} message${s.message_count === 1 ? "" : "s"}`,
    }));
  }, [sessions]);

  // Handle selecting a chat session in the sidebar or settings modal
  async function handleSelectChat(sessionId: string) {
    setActiveChat(sessionId);
    if (isAuthenticated) {
      try {
        const historyRes = await chatApi.history(sessionId);
        const historyMsgs: ChatMessageData[] = historyRes.data.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          createdAt: new Date(m.created_at),
          confidence: m.confidence,
          // Preserve full citation including id and relevance
          citations: m.citations,
        }));
        setMessages(historyMsgs);
      } catch (err) {
        toast.error("Failed to load chat history");
      }
    }
  }

  const removeDoc = useCallback((docId: string) => {
    setDocs((current) => {
      const removing = current.find((d) => d.id === docId);
      if (removing?.previewUrl && blobUrlsRef.current.has(removing.previewUrl)) {
        URL.revokeObjectURL(removing.previewUrl);
        blobUrlsRef.current.delete(removing.previewUrl);
      }
      return current.filter((d) => d.id !== docId);
    });
  }, []);

  async function addFiles(files: File[]) {
    if (files.length === 0) return;

    // Optimistic UI update
    const added = files.map<UploadedDoc>((file) => {
      const kind = kindFromName(file.name);
      let previewUrl: string | undefined;
      if (kind === "image") {
        previewUrl = URL.createObjectURL(file);
        blobUrlsRef.current.add(previewUrl);
      }
      return {
        id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        name: file.name,
        kind,
        typeLabel: typeLabel(kind),
        uploadedAt: new Date(),
        pages: kind === "image" ? 1 : Math.max(1, Math.round(file.size / 42000) || 6),
        previewUrl,
      };
    });
    setDocs((current) => [...added, ...current]);

    // Real upload if authenticated
    if (isAuthenticated) {
      try {
        await documentsApi.upload(files);
        toast.success(`${files.length} file${files.length > 1 ? "s" : ""} uploaded and indexed!`);

        try {
          const result = await documentsApi.list();
          const serverDocs: UploadedDoc[] = result.data.map((doc) => ({
            id: doc.id,
            name: doc.name,
            kind: kindFromName(doc.name),
            typeLabel: typeLabel(kindFromName(doc.name)),
            uploadedAt: new Date(doc.uploaded_at),
            pages: doc.pages,
            previewUrl: undefined,
          }));
          setDocs(serverDocs);
        } catch {
          // Non-fatal
        }
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : "Upload failed");
        setDocs((current) => {
          const filtered = current.filter((d) => !added.some((a) => a.id === d.id));
          added.forEach((a) => {
            if (a.previewUrl && blobUrlsRef.current.has(a.previewUrl)) {
              URL.revokeObjectURL(a.previewUrl);
              blobUrlsRef.current.delete(a.previewUrl);
            }
          });
          return filtered;
        });
      }
    } else {
      toast.success(`${added.length} file${added.length > 1 ? "s" : ""} added (guest mode — not saved)`);
    }
  }

  // FIX: regenerate sends the last user message, not the empty input
  function handleRegenerate() {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUserMsg) return;
    setInput(lastUserMsg.content);
    // Remove last assistant response to re-ask
    setMessages((current) => {
      const lastAssistantIdx = [...current].map((m, i) => ({ m, i })).reverse().find(({ m }) => m.role === "assistant");
      if (lastAssistantIdx) return current.slice(0, lastAssistantIdx.i);
      return current;
    });
    // Small timeout to let state update, then send
    setTimeout(() => {
      sendMessage(lastUserMsg.content);
    }, 50);
  }

  // Core send function — accepts optional explicit text (used by regenerate)
  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;
    setMessages((current) => [
      ...current,
      { id: `u-${Date.now()}`, role: "user", content: text, createdAt: new Date() },
    ]);
    setInput("");
    setLoading(true);

    if (isAuthenticated) {
      try {
        const sessionId = activeChat ?? undefined;
        const res = await chatApi.send(text, sessionId);
        const d = res.data;

        if (d.session_id && !activeChat) {
          setActiveChat(d.session_id);
        }

        setMessages((current) => [
          ...current,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: d.answer,
            createdAt: new Date(),
            confidence: d.confidence ?? undefined,
            status: d.status,
            // FIX: preserve all citation fields including id and relevance
            citations: d.citations.map((c) => ({
              id: c.id,
              source: c.source,
              page: c.page,
              snippet: c.snippet,
              relevance: c.relevance,
            })),
          },
        ]);

        // Refresh sessions list after sending so new sessions appear in sidebar
        loadSessions();
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : "Failed to get answer");
      } finally {
        setLoading(false);
      }
    } else {
      // Guest / demo mode — use sample answer
      window.setTimeout(() => {
        setMessages((current) => [
          ...current,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: sampleAnswer,
            createdAt: new Date(),
            confidence: 0.89,
            citations: sampleCitations,
          },
        ]);
        setLoading(false);
      }, 1600);
    }
  }

  function send() {
    sendMessage(input.trim());
  }

  function handleStop() {
    setLoading(false);
    toast("Response stopped.");
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* ── Left sidebar ── */}
      <AnalyzerSidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        docs={docs}
        chats={sidebarChats}
        activeChat={activeChat}
        onSelectChat={handleSelectChat}
        onNewChat={() => {
          setMessages([]);
          setActiveChat(null);
          toast.success("Started a new chat");
        }}
        onUpload={() => setUploadOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        search={search}
        onSearch={setSearch}
      />

      {/* ── Main content column ── */}
      <div className="ambient-glow flex min-w-0 flex-1 flex-col">
        {/* Top navbar */}
        <Navbar
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onTogglePanel={() => setPanelOpen((v) => !v)}
          panelOpen={panelOpen}
          theme={theme}
          onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          docCount={docs.length}
        />

        {/* ── Scrollable chat area ── */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {/* ── Empty / Welcome state — ChatGPT style ── */}
          {!hasMessages && !loading && (
            <div className="flex h-full flex-col items-center justify-center px-4 py-12 text-center">
              {/* Brand logo */}
              <div className="relative mb-6">
                <span className="absolute inset-0 -z-10 rounded-full blur-3xl gradient-brand opacity-20" />
                <span className="grid h-20 w-20 place-items-center rounded-3xl gradient-brand shadow-xl">
                  <BrainCircuit className="h-10 w-10 text-white" />
                </span>
              </div>
              <h1 className="text-3xl font-bold sm:text-4xl">
                <span className="gradient-text">What can I help with?</span>
              </h1>
              <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
                Ask me anything — general knowledge, coding problems, or questions about your
                uploaded documents. Answers grounded in your files include citations and page
                numbers.
              </p>

              {/* Suggested prompts */}
              <div className="mt-8 grid w-full max-w-xl gap-2 sm:grid-cols-2">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => {
                      setInput(prompt);
                      setTimeout(() => sendMessage(prompt), 50);
                    }}
                    className="group rounded-2xl border border-border/60 bg-card/60 px-4 py-3 text-left text-sm text-muted-foreground transition-all hover:border-primary/50 hover:bg-accent hover:text-foreground"
                  >
                    <Sparkles className="mb-1 h-4 w-4 text-chart-2 transition-colors group-hover:text-primary" />
                    {prompt}
                  </button>
                ))}
              </div>

              {/* Document count badge */}
              {docs.length > 0 && (
                <p className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <FileText className="h-3.5 w-3.5 text-chart-1" />
                  {docs.length} document{docs.length !== 1 ? "s" : ""} loaded
                </p>
              )}
            </div>
          )}

          {/* ── Chat messages ── */}
          {(hasMessages || loading) && (
            <div className="mx-auto w-full max-w-3xl space-y-6 px-1 py-6 sm:px-2">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  onRegenerate={handleRegenerate}
                />
              ))}
              {loading && <TypingIndicator />}
            </div>
          )}

          {/* ── Documents panel (shown when docs exist and no messages yet) ── */}
          {!hasMessages && !loading && docs.length > 0 && (
            <div className="mx-auto w-full max-w-3xl px-4 pb-6">
              <Tabs defaultValue="documents">
                <TabsList className="w-full">
                  <TabsTrigger value="documents" className="flex-1">
                    Documents ({fileDocs.length})
                  </TabsTrigger>
                  <TabsTrigger value="images" className="flex-1">
                    Images ({imageDocs.length})
                  </TabsTrigger>
                  <TabsTrigger value="upload" className="flex-1">
                    Add files
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="documents" className="mt-3 grid gap-2 sm:grid-cols-2">
                  {fileDocs.map((doc) => (
                    <UploadCard
                      key={doc.id}
                      doc={doc}
                      onDelete={() => {
                        removeDoc(doc.id);
                        toast("Document removed");
                      }}
                    />
                  ))}
                  {fileDocs.length === 0 && (
                    <p className="text-xs text-muted-foreground">No documents yet.</p>
                  )}
                </TabsContent>
                <TabsContent value="images" className="mt-3 grid gap-2 sm:grid-cols-3">
                  {imageDocs.map((doc) => (
                    <ImagePreviewCard
                      key={doc.id}
                      doc={doc}
                      onDelete={() => {
                        removeDoc(doc.id);
                        toast("Image removed");
                      }}
                    />
                  ))}
                  {imageDocs.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      Upload a photo of a handwritten or printed paper.
                    </p>
                  )}
                </TabsContent>
                <TabsContent value="upload" className="mt-3">
                  <UploadDropzone onFiles={addFiles} compact />
                </TabsContent>
              </Tabs>
            </div>
          )}

          {/* Loading spinner for docs */}
          {docsLoading && (
            <div className="mt-6 text-center text-sm text-muted-foreground">
              Loading your documents…
            </div>
          )}
        </div>

        {/* ── Chat composer — always visible at bottom ── */}
        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={send}
          onStop={handleStop}
          onFiles={addFiles}
          loading={loading}
        />
      </div>

      {/* ── Right analyzer panel ── */}
      <AnalyzerPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        paperCount={docs.length}
      />

      {/* ── Upload dialog ── */}
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload documents</DialogTitle>
          </DialogHeader>
          <UploadDropzone
            onFiles={(files) => {
              addFiles(files);
              setUploadOpen(false);
            }}
          />
        </DialogContent>
      </Dialog>

      {/* ── User Settings Modal ── */}
      <UserSettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        sessions={sessions}
        onSelectSession={handleSelectChat}
        onRefreshSessions={loadSessions}
      />
    </div>
  );
}
