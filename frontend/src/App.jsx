import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Show, SignIn, useAuth, useUser } from "@clerk/react";
import { Toaster, toast } from "sonner";
import { useApi } from "./hooks/useApi.js";
import { cacheKeySource, sha256Hex } from "./lib/hashQuery.js";
import { createLruCache } from "./lib/lruCache.js";
import {
  idbClearAccount,
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
import ModeSelector from "./components/ModeSelector";
import QueryInput from "./components/QueryInput";
import ResponsePanel from "./components/ResponsePanel";
import ConfirmModal from "./components/ConfirmModal";

function extractDocumentIds(response) {
  const ids = new Set();
  for (const ch of response?.retrieved_chunks || []) {
    const id = ch.metadata?.document_id;
    if (id) ids.add(String(id));
  }
  return [...ids];
}

function buildCachePayload(query, response) {
  return {
    query,
    answer: response.answer,
    context: response.retrieved_chunks,
    trace: response.trace,
    agentSteps: response.agent_steps,
    metrics: response.metrics,
    timestamp: new Date().toISOString(),
    documentIds: extractDocumentIds(response)
  };
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
    getSessionMetrics,
  } = useApi();

  const [sessionId, setSessionId] = useState("");
  const [sessions, setSessions] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("auto");
  const [activeTab, setActiveTab] = useState("Answer");
  const [response, setResponse] = useState(null);
  const [history, setHistory] = useState([]);
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
    setResponse(null);
    setQuery("");
    setHistory([]);
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

  const refreshSideData = useCallback(async () => {
    if (!sessionId || !accountId) return;
    try {
      const [sessionsPayload, historyPayload, docsPayload, metricsPayload, sessionMetricsPayload] =
        await Promise.all([
          listSessions().catch(() => []),
          getHistory(sessionId),
          listDocuments(sessionId),
          getMetrics(),
          getSessionMetrics(sessionId)
        ]);
      setSessions(Array.isArray(sessionsPayload) ? sessionsPayload : []);
      setHistory(historyPayload.turns || []);
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

  const applyCachedResponse = useCallback(
    (cached, layer) => {
      const hitAt = new Date().toISOString();
      setResponse({
        ...cached.response,
        metrics: mergeClientCacheMetrics(cached.response.metrics || {}, layer, hitAt)
      });
      setHasCompletedTurn(true);
      setActiveTab("Answer");
      toast.message(`Served from ${layer} cache`, { description: hitAt });
    },
    []
  );

  async function submitQuery() {
    if (!query.trim() || isQuerying || !sessionId) return;
    setIsQuerying(true);
    setError("");
    setActiveTab("Answer");
    const q = query.trim();
    const payload = {
      query: q,
      session_id: sessionId,
      mode
    };

    const keySrc = cacheKeySource(sessionId, mode, q);
    const hashKey = await sha256Hex(keySrc);

    const mem = memoryCacheRef.current.get(hashKey);
    if (mem?.response) {
      applyCachedResponse(mem, "memory");
      setQuery("");
      setIsQuerying(false);
      await refreshSideData();
      return;
    }

    try {
      const idbRow = await idbGet(accountId, hashKey);
      if (idbRow?.response) {
        memoryCacheRef.current.set(hashKey, idbRow);
        applyCachedResponse(idbRow, "persisted");
        setQuery("");
        setIsQuerying(false);
        await refreshSideData();
        return;
      }
    } catch {
      /* ignore idb */
    }

    setResponse({
      answer: "",
      session_id: sessionId,
      mode_used: mode,
      citations: [],
      retrieved_chunks: [],
      agent_steps: [],
      trace: [],
      metrics: {},
      request_id: "streaming"
    });

    const finalizeAndStore = async (finalResponse) => {
      setResponse(finalResponse);
      if (finalResponse?.error) {
        setError(finalResponse.answer || "Temporary issue, retrying...");
        return;
      }
      setHasCompletedTurn(true);
      const entry = {
        response: finalResponse,
        raw: buildCachePayload(q, finalResponse)
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
          setResponse((current) => ({
            ...(current || {}),
            answer: `${current?.answer || ""}${token}`
          }));
        },
        async (finalResponse) => {
          await finalizeAndStore(finalResponse);
        },
        (event) => {
          if (event?.answer) setError(event.answer);
        }
      );
      setQuery("");
      await refreshSideData();
    } catch (err) {
      try {
        const fallback = await queryCopilot(payload);
        await finalizeAndStore(fallback);
        if (fallback?.error) {
          setError(fallback.answer || "Temporary issue, retrying...");
        }
        setQuery("");
        await refreshSideData();
      } catch (fallbackError) {
        setError(fallbackError.message || err.message);
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
    setResponse(null);
    setHistory([]);
    toast.success("New session");
  }

  function handleSelectSession(sid) {
    setActiveSessionId(accountId, sid);
    setSessionId(sid);
    setResponse(null);
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
    memoryCacheRef.current.clear();
    toast.success("In-memory cache cleared for this browser tab");
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

  const selectedMetrics = useMemo(() => {
    const base = response?.metrics || metricsSnapshot || {};
    return base;
  }, [response, metricsSnapshot]);

  const routeBadge = response
    ? `${response.mode_used} / ${selectedMetrics.route_decision || "route"}`
    : "idle";

  const role =
    user?.publicMetadata?.role ||
    user?.unsafeMetadata?.role ||
    (Array.isArray(user?.organizationMemberships) &&
      user.organizationMemberships[0]?.role) ||
    "";

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
            sessionId={sessionId}
            sessions={sessions}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onDeleteSession={requestDeleteSession}
            history={history}
            documents={documents}
            routeBadge={routeBadge}
            isUploading={isUploading}
            handleUpload={handleUpload}
            uploadStatus={uploadStatus}
            setResponse={setResponse}
            onDeleteFile={requestDeleteFile}
            onClearSessionCache={handleClearSessionCache}
            onClearAllCache={handleClearAllCache}
          />

          <div className="workspace-column">
            <AppHeader
              subtitle={routeBadge}
              accountName={user?.fullName || user?.primaryEmailAddress?.emailAddress || "User"}
              role={role}
            />

            <section className="workspace">
              <div className="main-content">
                <ModeSelector
                  mode={mode}
                  setMode={setMode}
                  showSources={showSources}
                  setShowSources={setShowSources}
                  showTrace={showTrace}
                  setShowTrace={setShowTrace}
                />

                <QueryInput
                  query={query}
                  setQuery={setQuery}
                  submitQuery={submitQuery}
                  handleQueryKeyDown={handleQueryKeyDown}
                  isQuerying={isQuerying}
                  suggestedQueries={suggestedQueries}
                />

                {error && (
                  <div className="error-banner glass-panel">
                    <AlertCircle size={18} className="danger" />
                    <span className="danger">{error}</span>
                  </div>
                )}

                <ResponsePanel
                  response={response}
                  activeTab={activeTab}
                  setActiveTab={setActiveTab}
                  showSources={showSources}
                  showTrace={showTrace}
                  isQuerying={isQuerying}
                  metricsSnapshot={selectedMetrics}
                  sessionMetrics={sessionMetrics}
                  hasCompletedTurn={hasCompletedTurn}
                />
              </div>
            </section>
          </div>
        </div>
      </Show>
    </>
  );
}
