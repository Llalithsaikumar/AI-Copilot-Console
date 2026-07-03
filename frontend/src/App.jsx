import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Show, SignIn, useUser } from "@clerk/react";
import { Toaster, toast } from "sonner";
import { useApi } from "./hooks/useApi.js";
import { cacheKeySource, sha256Hex } from "./lib/hashQuery.js";
import { createLruCache } from "./lib/lruCache.js";
import {
  idbClearAccount,
  idbClearSession,
  idbGet,
  idbInvalidateByDocumentId,
  idbSet
} from "./lib/idbCache.js";
import {
  getActiveSessionId,
  readSessionRegistry,
  setActiveSessionId,
  upsertSessionRecord,
  writeSessionRegistry
} from "./lib/accountStorage.js";

import Sidebar from "./components/Sidebar";
import AppHeader from "./components/AppHeader";
import ChatThread from "./components/ChatThread";
import Composer from "./components/Composer";
import ConfirmModal from "./components/ConfirmModal";

/* Monotonic id source for thread messages (avoids key collisions). */
let msgSeq = 0;
function makeId(prefix) {
  msgSeq += 1;
  return `${prefix}-${Date.now()}-${msgSeq}`;
}

function extractDocumentIds(response) {
  const ids = new Set();
  for (const ch of response?.retrieved_chunks || []) {
    const id = ch.metadata?.document_id;
    if (id) ids.add(String(id));
  }
  return [...ids];
}

function buildCachePayload(query, response, sessionId) {
  return {
    query,
    sessionId,
    answer: response.answer,
    context: response.retrieved_chunks,
    trace: response.trace,
    agentSteps: response.agent_steps,
    metrics: response.metrics,
    timestamp: new Date().toISOString(),
    documentIds: extractDocumentIds(response)
  };
}

/* Map a backend query response → a thread assistant message. */
function responseToMessage(response, opts = {}) {
  return {
    id: opts.id || makeId("a"),
    role: "assistant",
    content: response.answer || "",
    mode: response.mode_used,
    citations: response.citations || [],
    chunks: response.retrieved_chunks || [],
    agentSteps: response.agent_steps || [],
    trace: response.trace || [],
    metrics: response.metrics || {},
    error: !!response.error,
    streaming: opts.streaming ?? false
  };
}

/* Rebuild the thread from server-side session history (user+assistant pairs). */
function historyToMessages(turns) {
  const out = [];
  for (const turn of turns || []) {
    const meta = turn.metadata || {};
    out.push({ id: `u-${turn.id}`, role: "user", content: turn.user_input, mode: turn.mode_used });
    out.push({
      id: `a-${turn.id}`,
      role: "assistant",
      content: turn.system_response,
      mode: turn.mode_used,
      citations: meta.citations || [],
      chunks: meta.retrieved_chunks || [],
      agentSteps: [],
      trace: meta.trace || [],
      metrics: meta.metrics || {},
      error: false,
      streaming: false
    });
  }
  return out;
}

export default function App() {
  const { user } = useUser();
  const accountId = user?.id;
  const {
    generateSessionId,
    queryCopilot,
    queryCopilotStream,
    uploadDocument,
    listDocuments,
    deleteDocument,
    listSessions,
    getHistory,
    deleteSession,
    getMetrics,
    getSessionMetrics
  } = useApi();

  const [sessionId, setSessionId] = useState("");
  const [sessions, setSessions] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [mode, setMode] = useState("auto");
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [metricsSnapshot, setMetricsSnapshot] = useState(null);
  const [sessionMetrics, setSessionMetrics] = useState(null);
  const [showSources, setShowSources] = useState(true);
  const [showTrace, setShowTrace] = useState(true);
  const [isQuerying, setIsQuerying] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");
  const [suggestedQueries, setSuggestedQueries] = useState([]);
  const [confirm, setConfirm] = useState(null);
  const [hasCompletedTurn, setHasCompletedTurn] = useState(false);

  const memoryCacheRef = useRef(createLruCache(64));

  useEffect(() => {
    if (!accountId) return;
    memoryCacheRef.current.clear();
    setMessages([]);
    setQuery("");
    setSessions([]);
    setDocuments([]);
    setHasCompletedTurn(false);
    let sid = getActiveSessionId(accountId);
    if (!sid || !sid.startsWith(`${accountId}:`)) {
      generateSessionId().then(newSid => {
        setActiveSessionId(accountId, newSid);
        upsertSessionRecord(accountId, {
          sessionId: newSid,
          accountId,
          mode: "auto",
          createdAt: new Date().toISOString(),
          lastActiveAt: new Date().toISOString()
        });
        setSessionId(newSid);
      }).catch(console.error);
    } else {
      setSessionId(sid);
    }
  }, [accountId, generateSessionId]);

  // Seed the thread from server history whenever the active session changes.
  // Guarded on sessionId only, so it never clobbers a live stream mid-turn.
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return undefined;
    }
    let cancelled = false;
    getHistory(sessionId)
      .then((payload) => {
        if (!cancelled) setMessages(historyToMessages(payload?.turns || []));
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const refreshSideData = useCallback(async () => {
    if (!sessionId || !accountId) return;
    try {
      const [sessionsPayload, docsPayload, metricsPayload, sessionMetricsPayload] =
        await Promise.all([
          listSessions().catch(() => []),
          listDocuments(sessionId),
          getMetrics(),
          getSessionMetrics(sessionId)
        ]);
      setSessions(Array.isArray(sessionsPayload) ? sessionsPayload : []);
      setDocuments(docsPayload || []);
      setMetricsSnapshot(metricsPayload || null);
      setSessionMetrics(sessionMetricsPayload || null);

      for (const row of sessionsPayload || []) {
        upsertSessionRecord(accountId, {
          sessionId: row.session_id,
          accountId,
          mode: row.mode || "auto",
          createdAt: row.last_active_at,
          lastActiveAt: row.last_active_at,
          lastQueryPreview: row.last_query_preview
        });
      }
    } catch {
      setMetricsSnapshot(null);
      setSessionMetrics(null);
    }
  }, [sessionId, accountId]);

  useEffect(() => {
    refreshSideData();
  }, [refreshSideData]);

  const mergeClientCacheMetrics = (baseMetrics, layer, hitAt) => ({
    ...baseMetrics,
    client_cache_hit: true,
    client_cache_layer: layer,
    client_cache_hit_at: hitAt
  });

  const markClientCacheTrace = (trace = [], layer, hitAt) => {
    const original = Array.isArray(trace) ? trace : [];
    let sawCacheCheck = false;
    const patched = original.map((step) => {
      if (step?.step !== "cache_check") return step;
      sawCacheCheck = true;
      return {
        ...step,
        meta: {
          ...(step.meta || {}),
          hit: true,
          layer,
          source: "client",
          hit_at: hitAt
        }
      };
    });
    if (!sawCacheCheck) {
      patched.unshift({
        step: "cache_check",
        meta: { hit: true, layer, source: "client", hit_at: hitAt }
      });
    }
    patched.push({
      step: "client_cache_return",
      meta: {
        layer,
        hit_at: hitAt,
        cached_trace_steps: original.length
      }
    });
    return patched;
  };

  const pushCachedMessage = useCallback((cachedResponse, layer) => {
    const hitAt = new Date().toISOString();
    const merged = {
      ...cachedResponse,
      trace: markClientCacheTrace(cachedResponse.trace, layer, hitAt),
      metrics: mergeClientCacheMetrics(cachedResponse.metrics || {}, layer, hitAt)
    };
    setMessages((prev) => [...prev, responseToMessage(merged, { streaming: false })]);
    setHasCompletedTurn(true);
    toast.message(`Served from ${layer} cache`, { description: hitAt });
  }, []);

  async function submitQuery(opts = {}) {
    const skipCache = opts.skipCache === true;
    const isRegen = opts.regenerate === true;
    const q = (opts.overrideQuery ?? query).trim();
    if (!q || isQuerying || !sessionId) return;
    setIsQuerying(true);
    setError("");
    setLastQuery(q);
    const payload = { query: q, session_id: sessionId, mode };

    const keySrc = cacheKeySource(sessionId, mode, q);
    const hashKey = await sha256Hex(keySrc);

    if (!isRegen) {
      setMessages((prev) => [...prev, { id: makeId("u"), role: "user", content: q, mode }]);
    }

    const mem = skipCache ? null : memoryCacheRef.current.get(hashKey);
    if (mem?.response) {
      pushCachedMessage(mem.response, "memory");
      setQuery("");
      setIsQuerying(false);
      await refreshSideData();
      return;
    }

    if (!skipCache) {
      try {
        const idbRow = await idbGet(accountId, hashKey);
        if (idbRow?.response) {
          memoryCacheRef.current.set(hashKey, idbRow);
          pushCachedMessage(idbRow.response, "persisted");
          setQuery("");
          setIsQuerying(false);
          await refreshSideData();
          return;
        }
      } catch {
        /* ignore idb */
      }
    }

    const assistantId = makeId("a");
    const placeholder = {
      id: assistantId,
      role: "assistant",
      content: "",
      mode,
      citations: [],
      chunks: [],
      agentSteps: [],
      trace: [],
      metrics: {},
      error: false,
      streaming: true
    };
    setMessages((prev) => {
      const base =
        isRegen && prev.length && prev[prev.length - 1].role === "assistant"
          ? prev.slice(0, -1)
          : prev;
      return [...base, placeholder];
    });
    setQuery("");

    const patchAssistant = (patch) =>
      setMessages((prev) =>
        prev.map((mmsg) => (mmsg.id === assistantId ? { ...mmsg, ...patch } : mmsg))
      );

    const finalizeAndStore = async (finalResponse) => {
      const built = responseToMessage(finalResponse, { id: assistantId, streaming: false });
      if (finalResponse?.error) {
        setError(finalResponse.answer || "Temporary issue, retrying...");
        patchAssistant({ ...built, error: true, streaming: false });
        return;
      }
      patchAssistant({ ...built, streaming: false });
      setHasCompletedTurn(true);
      const entry = {
        sessionId,
        response: finalResponse,
        raw: buildCachePayload(q, finalResponse, sessionId)
      };
      memoryCacheRef.current.set(hashKey, entry);
      try {
        await idbSet(accountId, hashKey, entry);
      } catch {
        /* ignore */
      }
      upsertSessionRecord(accountId, {
        sessionId,
        accountId,
        mode,
        lastActiveAt: new Date().toISOString(),
        lastQueryPreview: q
      });
    };

    try {
      await queryCopilotStream(
        payload,
        (token) => {
          setMessages((prev) =>
            prev.map((mmsg) =>
              mmsg.id === assistantId ? { ...mmsg, content: `${mmsg.content}${token}` } : mmsg
            )
          );
        },
        async (finalResponse) => {
          await finalizeAndStore(finalResponse);
        },
        (event) => {
          const message = event?.answer || event?.message;
          if (message) setError(message);
        }
      );
      await refreshSideData();
    } catch (err) {
      try {
        const fallback = await queryCopilot(payload);
        await finalizeAndStore(fallback);
        if (fallback?.error) {
          setError(fallback.answer || "Temporary issue, retrying...");
        }
        await refreshSideData();
      } catch (fallbackError) {
        const msg = fallbackError.message || err.message;
        setError(msg);
        patchAssistant({ streaming: false, error: true, content: msg });
      }
    } finally {
      setIsQuerying(false);
    }
  }

  function handleQueryKeyDown(event) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    submitQuery();
  }

  function handleRegenerate() {
    if (!lastQuery || isQuerying) return;
    submitQuery({ overrideQuery: lastQuery, skipCache: true, regenerate: true });
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setError("");
    setUploadStatus("");
    try {
      const payload = await uploadDocument(file, sessionId);
      setUploadStatus(
        `${payload.file_name}: ${payload.chunks_indexed} indexed, ${payload.chunks_skipped} skipped (${payload.status})`
      );
      setSuggestedQueries(payload.suggested_queries || []);
      await refreshSideData();
      toast.success("File uploaded");
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  async function handleNewSession() {
    if (!accountId) return;
    const sid = await generateSessionId();
    setActiveSessionId(accountId, sid);
    upsertSessionRecord(accountId, {
      sessionId: sid,
      accountId,
      mode,
      createdAt: new Date().toISOString(),
      lastActiveAt: new Date().toISOString()
    });
    setSessionId(sid);
    setMessages([]);
    setSuggestedQueries([]);
    toast.success("New session");
  }

  function handleSelectSession(sid) {
    setActiveSessionId(accountId, sid);
    setSessionId(sid);
  }

  function requestDeleteSession(sid) {
    setConfirm({
      title: "Delete session?",
      message: "Removes server-side conversation history for this session.",
      danger: true,
      onConfirm: async () => {
        try {
          await deleteSession(sid);
          const reg = readSessionRegistry(accountId).filter((x) => x.sessionId !== sid);
          writeSessionRegistry(accountId, reg);
          toast.success("Session cleared");
          if (sid === sessionId) {
            handleNewSession();
          }
          await refreshSideData();
        } catch (e) {
          toast.error(e.message);
        }
        setConfirm(null);
      }
    });
  }

  function requestDeleteFile(doc) {
    setConfirm({
      title: "Delete file?",
      message: `Remove ${doc.file_name} from the index and invalidate matching cache entries.`,
      danger: true,
      onConfirm: async () => {
        try {
          await deleteDocument(doc.document_id);
          await idbInvalidateByDocumentId(accountId, doc.document_id);
          memoryCacheRef.current.clear();
          toast.success("File deleted");
          await refreshSideData();
        } catch (e) {
          toast.error(e.message);
        }
        setConfirm(null);
      }
    });
  }

  async function handleClearSessionCache() {
    try {
      await idbClearSession(accountId, sessionId);
      memoryCacheRef.current.clear();
      toast.success("Query cache cleared for this session");
    } catch {
      memoryCacheRef.current.clear();
      toast.warning("Cleared memory cache; persisted cache could not be cleared");
    }
  }

  async function handleClearAllCache() {
    setConfirm({
      title: "Clear all persisted cache?",
      message: "Removes all IndexedDB cached query responses for your account on this device.",
      danger: true,
      onConfirm: async () => {
        try {
          await idbClearAccount(accountId);
          memoryCacheRef.current.clear();
          toast.success("Cache cleared");
        } catch {
          toast.error("Could not clear cache");
        }
        setConfirm(null);
      }
    });
  }

  const latestAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") return messages[i];
    }
    return null;
  }, [messages]);

  const selectedMetrics = useMemo(
    () => latestAssistant?.metrics || metricsSnapshot || {},
    [latestAssistant, metricsSnapshot]
  );

  const headerResponse = latestAssistant
    ? {
        answer: latestAssistant.content,
        error: latestAssistant.error,
        metrics: latestAssistant.metrics,
        mode_used: latestAssistant.mode
      }
    : null;

  const routeBadge = latestAssistant
    ? `${latestAssistant.mode || mode} / ${selectedMetrics.route_decision || "route"}`
    : "idle";

  const role =
    user?.publicMetadata?.role ||
    user?.unsafeMetadata?.role ||
    (Array.isArray(user?.organizationMemberships) &&
      user.organizationMemberships[0]?.role) ||
    "";

  const accountName =
    user?.fullName || user?.primaryEmailAddress?.emailAddress || "User";
  const userInitials = accountName
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <>
      <Show when="signed-out">
        <div className="login-screen">
          <div className="login-brand">
            <h1>AI Copilot Console</h1>
            <p>Welcome back. Sign in to continue.</p>
          </div>
          <SignIn />
        </div>
      </Show>

      <Show when="signed-in">
        <Toaster richColors position="top-center" />
        <ConfirmModal
          open={!!confirm}
          title={confirm?.title}
          message={confirm?.message}
          danger={confirm?.danger}
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            void confirm?.onConfirm?.();
          }}
        />
        <div className="app-layout">
          <Sidebar
            collapsed={sidebarCollapsed}
            setCollapsed={setSidebarCollapsed}
            accountId={accountId}
            sessionId={sessionId}
            sessions={sessions}
            sessionMetrics={sessionMetrics}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onDeleteSession={requestDeleteSession}
            documents={documents}
            routeBadge={routeBadge}
            isUploading={isUploading}
            handleUpload={handleUpload}
            uploadStatus={uploadStatus}
            onDeleteFile={requestDeleteFile}
            onClearSessionCache={handleClearSessionCache}
            onClearAllCache={handleClearAllCache}
          />

          <div className="workspace-column">
            <AppHeader
              subtitle={routeBadge}
              accountName={accountName}
              role={role}
              metrics={selectedMetrics}
              response={headerResponse}
              mode={mode}
              isQuerying={isQuerying}
              hasCompletedTurn={hasCompletedTurn}
            />

            <section className="workspace">
              <ChatThread
                messages={messages}
                isQuerying={isQuerying}
                mode={mode}
                hasCompletedTurn={hasCompletedTurn}
                showSources={showSources}
                showTrace={showTrace}
                sessionMetrics={sessionMetrics}
                onRegenerate={handleRegenerate}
                canRegenerate={!!lastQuery}
                userInitials={userInitials}
                welcomeSuggestions={suggestedQueries}
                onPickSuggestion={(text) => setQuery(text)}
              />

              {error && (
                <div className="error-banner">
                  <AlertCircle size={18} className="danger" />
                  <span className="danger">{error}</span>
                </div>
              )}

              <Composer
                query={query}
                setQuery={setQuery}
                submitQuery={submitQuery}
                handleQueryKeyDown={handleQueryKeyDown}
                isQuerying={isQuerying}
                suggestedQueries={suggestedQueries}
                mode={mode}
                setMode={setMode}
                showSources={showSources}
                setShowSources={setShowSources}
                showTrace={showTrace}
                setShowTrace={setShowTrace}
              />
            </section>
          </div>
        </div>
      </Show>
    </>
  );
}
