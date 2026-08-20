import { useEffect, useMemo, useRef, useState, useCallback, lazy, Suspense } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AnalyzerSidebar, type SidebarChat } from "@/components/analyzer/AnalyzerSidebar";
import { Navbar } from "@/components/analyzer/Navbar";
import { ChatMessage, TypingIndicator } from "@/components/analyzer/ChatMessage";
import { ChatComposer } from "@/components/analyzer/ChatComposer";
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
import {
  chatApi,
  documentsApi,
  sessionsApi,
  type SessionResponse,
  type StreamMeta,
} from "@/lib/api";
import { BrainCircuit, FileText, Sparkles } from "lucide-react";

// Code-split heavy chart and modal dependencies
const AnalyzerPanel = lazy(() => import("@/components/analyzer/AnalyzerPanel"));
const UserSettingsModal = lazy(() =>
  import("@/components/analyzer/UserSettingsModal").then((m) => ({ default: m.UserSettingsModal })),
);
const SearchPadModal = lazy(() =>
  import("@/components/analyzer/SearchPadModal").then((m) => ({ default: m.SearchPadModal })),
);

export const Route = createFileRoute("/")(
  Object.assign(
    {}
    ,
    {
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
    }
  ) as unknown as undefined
);

// Suggested prompts shown on the empty state (ChatGPT style)
const SUGGESTED_PROMPTS = [
  "Which topics repeat most across all papers?",
  "Explain binary search with an example.",
  "What are the most important questions for the exam?",
  "Write a C++ program to implement BFS.",
];

// Session persistence key in sessionStorage
const SESSION_STORAGE_KEY = "ss_spark_active_chat";

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
  const [streamingPhase, setStreamingPhase] = useState<string>("");
  const [docsLoading, setDocsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [activeChat, setActiveChat] = useState<string | null>(() => {
    // Restore active session from sessionStorage so page refresh doesn't lose context
    try {
      return sessionStorage.getItem(SESSION_STORAGE_KEY);
    } catch {
      return null;
    }
  });
  const [uploadOpen, setUploadOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchPadOpen, setSearchPadOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Track blob URLs for cleanup to prevent memory leaks
  const blobUrlsRef = useRef<Set<string>>(new Set());

  // Race-condition prevention: track the current in-flight abort controller
  const abortControllerRef = useRef<AbortController | null>(null);

  // Lock to prevent double-submit (race between button click and Enter key)
  const sendingRef = useRef(false);

  // Ref-mirror of activeChat so async closures always see the latest value
  const activeChatRef = useRef<string | null>(activeChat);
  useEffect(() => {
    activeChatRef.current = activeChat;
    // Persist to sessionStorage
    try {
      if (activeChat) {
        sessionStorage.setItem(SESSION_STORAGE_KEY, activeChat);
      } else {
        sessionStorage.removeItem(SESSION_STORAGE_KEY);
      }
    } catch {
      /* ignore */
    }
  }, [activeChat]);

  // Smart auto-scroll: only scroll if user is near the bottom
  const autoScrollRef = useRef(true);
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    autoScrollRef.current = distanceFromBottom < 120;
  }, []);

  const scrollToBottom = useCallback((force = false) => {
    const el = scrollRef.current;
    if (!el) return;
    if (force || autoScrollRef.current) {
      requestAnimationFrame(() => {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      });
    }
  }, []);

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

  // Load active chat history on mount if we have a stored active session
  useEffect(() => {
    if (!isAuthenticated || !activeChat) return;

    async function restoreHistory() {
      try {
        const historyRes = await chatApi.history(activeChat!);
        if (historyRes.data.length > 0) {
          const historyMsgs: ChatMessageData[] = historyRes.data.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            createdAt: new Date(m.created_at),
            confidence: m.confidence,
            citations: m.citations,
          }));
          setMessages(historyMsgs);
          setTimeout(() => scrollToBottom(true), 100);
        }
      } catch {
        // Non-fatal — just start fresh
      }
    }

    restoreHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]); // Only run once on mount

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

  // Auto-scroll to bottom when new messages arrive (respects user scroll position)
  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  // Cleanup blob URLs and abort any in-flight request on unmount
  useEffect(() => {
    const currentBlobUrls = blobUrlsRef.current;
    return () => {
      currentBlobUrls.forEach((url) => URL.revokeObjectURL(url));
      currentBlobUrls.clear();
      abortControllerRef.current?.abort();
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
    // Abort any in-flight request when switching sessions
    abortControllerRef.current?.abort();
    setLoading(false);
    sendingRef.current = false;
    setStreamingPhase("");

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
          citations: m.citations,
        }));
        setMessages(historyMsgs);
        setTimeout(() => scrollToBottom(true), 100);
      } catch (err) {
        toast.error("Failed to load chat history");
      }
    }
  }

  const removeDoc = useCallback(
    async (docId: string) => {
      let previousDocs: UploadedDoc[] = [];
      let removedDoc: UploadedDoc | undefined;

      setDocs((current) => {
        previousDocs = current;
        removedDoc = current.find((d) => d.id === docId);
        return current.filter((d) => d.id !== docId);
      });

      if (isAuthenticated) {
        try {
          await documentsApi.delete(docId);
          if (removedDoc?.previewUrl && blobUrlsRef.current.has(removedDoc.previewUrl)) {
            URL.revokeObjectURL(removedDoc.previewUrl);
            blobUrlsRef.current.delete(removedDoc.previewUrl);
          }
          toast.success("Document removed from workspace");
        } catch (err: unknown) {
          setDocs(previousDocs);
          toast.error(err instanceof Error ? err.message : "Failed to delete document from server");
        }
      } else {
        if (removedDoc?.previewUrl && blobUrlsRef.current.has(removedDoc.previewUrl)) {
          URL.revokeObjectURL(removedDoc.previewUrl);
          blobUrlsRef.current.delete(removedDoc.previewUrl);
        }
        toast.info("Document removed");
      }
    },
    [isAuthenticated],
  );

  // ─── Core streaming send function ──────────────────────────────────────────
  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      // Prevent duplicate submission
      if (sendingRef.current) return;
      sendingRef.current = true;

      // Abort any previous in-flight request
      abortControllerRef.current?.abort();

      // Unique ID for this specific request — guards against stale closures
      const requestId = `req-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

      // Placeholder message IDs
      const userMsgId = `u-${Date.now()}`;
      const assistantMsgId = `a-${Date.now() + 1}`;

      setMessages((current) => [
        ...current,
        { id: userMsgId, role: "user", content: text, createdAt: new Date() },
      ]);
      setInput("");
      setLoading(true);
      setStreamingPhase("thinking");
      scrollToBottom(true);

      if (isAuthenticated) {
        // Capture the current session ID from the ref (not closure) so
        // a quick second send doesn't pick up the wrong session
        const sessionIdAtSend = activeChatRef.current ?? undefined;

        const controller = chatApi.sendStream(text, sessionIdAtSend, {
          onSession: (sid) => {
            // Set session ID as soon as the server acknowledges it
            if (!activeChatRef.current) {
              setActiveChat(sid);
            }
            // Update placeholder message with the real session
          },
          onPhase: (phase) => {
            setStreamingPhase(phase);
          },
          onReset: () => {
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === assistantMsgId);
              if (idx === -1) return current;
              const updated = [...current];
              updated[idx] = {
                ...updated[idx],
                content: "",
              };
              return updated;
            });
          },
          onToken: (token) => {
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === assistantMsgId);
              if (idx === -1) {
                // First token — add the assistant placeholder
                return [
                  ...current,
                  {
                    id: assistantMsgId,
                    role: "assistant",
                    content: token,
                    createdAt: new Date(),
                    isStreaming: true,
                  },
                ];
              }
              // Append token to the existing message
              const updated = [...current];
              updated[idx] = {
                ...updated[idx],
                content: updated[idx].content + token,
              };
              return updated;
            });
          },
          onMeta: (meta: StreamMeta) => {
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === assistantMsgId);
              if (idx === -1) return current;
              const updated = [...current];
              updated[idx] = {
                ...updated[idx],
                confidence: meta.confidence ?? undefined,
                citations: meta.citations,
                status: meta.status,
                isStreaming: false,
              };
              return updated;
            });
          },
          onError: (errMsg) => {
            // Show inline error message in chat
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === assistantMsgId);
              if (idx !== -1) {
                // Update existing placeholder with error
                const updated = [...current];
                updated[idx] = {
                  ...updated[idx],
                  content: errMsg,
                  status: "error",
                  isStreaming: false,
                };
                return updated;
              }
              // Add error as new message if no placeholder yet
              return [
                ...current,
                {
                  id: assistantMsgId,
                  role: "assistant",
                  content: errMsg,
                  createdAt: new Date(),
                  status: "error",
                  isStreaming: false,
                },
              ];
            });
          },
          onDone: () => {
            setLoading(false);
            setStreamingPhase("");
            sendingRef.current = false;
            // Mark streaming as finished on the message
            setMessages((current) => {
              const idx = current.findIndex((m) => m.id === assistantMsgId);
              if (idx === -1) return current;
              if (!current[idx].isStreaming) return current;
              const updated = [...current];
              updated[idx] = { ...updated[idx], isStreaming: false };
              return updated;
            });
            // Refresh sessions list after sending so new sessions appear in sidebar
            loadSessions();
          },
        });

        abortControllerRef.current = controller;
      } else {
        // Guest / demo mode — use sample answer
        window.setTimeout(() => {
          setMessages((current) => [
            ...current,
            {
              id: assistantMsgId,
              role: "assistant",
              content: sampleAnswer,
              createdAt: new Date(),
              confidence: 0.89,
              citations: sampleCitations,
            },
          ]);
          setLoading(false);
          setStreamingPhase("");
          sendingRef.current = false;
        }, 1600);
      }
    },
    [isAuthenticated, loadSessions, scrollToBottom],
  );

  const addFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;

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

      if (isAuthenticated) {
        try {
          const uploadRes = await documentsApi.upload(files);
          toast.success(`${files.length} file${files.length > 1 ? "s" : ""} uploaded and indexed!`);

          if (uploadRes.data && uploadRes.data.length > 0) {
            const previewMap = new Map<string, string>();
            added.forEach((d) => {
              if (d.previewUrl) previewMap.set(d.name, d.previewUrl);
            });
            const serverDocs: UploadedDoc[] = uploadRes.data.map((doc) => {
              const docName = doc.name || doc.filename || "Document";
              return {
                id: doc.id,
                name: docName,
                kind: kindFromName(docName),
                typeLabel: typeLabel(kindFromName(docName)),
                uploadedAt: new Date(doc.uploaded_at),
                pages: doc.pages,
                previewUrl: previewMap.get(docName) ?? previewMap.get(doc.filename),
              };
            });
            setDocs((current) => {
              const nonOptimistic = current.filter((d) => !added.some((a) => a.id === d.id));
              return [...serverDocs, ...nonOptimistic];
            });
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
    },
    [isAuthenticated],
  );

  const handleRegenerate = useCallback(() => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUserMsg) return;
    setInput(lastUserMsg.content);
    setMessages((current) => {
      const lastAssistantIdx = [...current].map((m, i) => ({ m, i })).reverse().find(({ m }) => m.role === "assistant");
      if (lastAssistantIdx) return current.slice(0, lastAssistantIdx.i);
      return current;
    });
    setTimeout(() => {
      sendMessage(lastUserMsg.content);
    }, 50);
  }, [messages, sendMessage]);

  const send = useCallback(() => {
    sendMessage(input.trim());
  }, [input, sendMessage]);

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setLoading(false);
    setStreamingPhase("");
    sendingRef.current = false;
    // Mark the streaming message as finished
    setMessages((current) => {
      // Find last streaming message (compatible with older ES targets)
      let idx = -1;
      for (let i = current.length - 1; i >= 0; i--) {
        if (current[i].isStreaming) { idx = i; break; }
      }
      if (idx === -1) return current;
      const updated = [...current];
      updated[idx] = { ...updated[idx], isStreaming: false };
      return updated;
    });
    toast("Response stopped.");
  }, []);

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
          // Abort in-flight request when starting a new chat
          abortControllerRef.current?.abort();
          setLoading(false);
          sendingRef.current = false;
          setStreamingPhase("");
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
          onOpenSearchPad={() => setSearchPadOpen(true)}
        />

        {/* ── Scrollable chat area ── */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto" onScroll={handleScroll}>
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
                <button
                  onClick={() => setSearchPadOpen(true)}
                  className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors cursor-pointer"
                >
                  <FileText className="h-3.5 w-3.5 text-chart-1" />
                  {docs.length} document{docs.length !== 1 ? "s" : ""} loaded · Click to open Search Pad
                </button>
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
              {loading && !messages.some((m) => m.isStreaming) && (
                <TypingIndicator phase={streamingPhase} />
              )}
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
                      onDelete={() => removeDoc(doc.id)}
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
                      onDelete={() => removeDoc(doc.id)}
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

      {/* ── Right analyzer panel (lazy-loaded with Recharts) ── */}
      <Suspense fallback={null}>
        <AnalyzerPanel
          open={panelOpen}
          onClose={() => setPanelOpen(false)}
          paperCount={docs.length}
        />
      </Suspense>

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

      {/* ── Search Pad & Document Workspace Modal (lazy-loaded) ── */}
      <Suspense fallback={null}>
        {searchPadOpen && (
          <SearchPadModal
            open={searchPadOpen}
            onOpenChange={setSearchPadOpen}
            docs={docs}
            onUploadFiles={addFiles}
            onDeleteDoc={removeDoc}
            onAskAboutDoc={(docName) => {
              setInput(`Tell me the main topics and important questions from ${docName}`);
            }}
          />
        )}
      </Suspense>

      {/* ── User Settings Modal (lazy-loaded) ── */}
      <Suspense fallback={null}>
        {settingsOpen && (
          <UserSettingsModal
            open={settingsOpen}
            onOpenChange={setSettingsOpen}
            sessions={sessions}
            onSelectSession={handleSelectChat}
            onRefreshSessions={loadSessions}
          />
        )}
      </Suspense>
    </div>
  );
}
