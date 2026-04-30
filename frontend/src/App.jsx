import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Database,
  FileText,
  History,
  Loader2,
  LogOut,
  Send,
  Upload
} from "lucide-react";
import {
  getSessionMetrics,
  getHistory,
  getMetrics,
  getMe,
  listDocuments,
  queryCopilot,
  queryCopilotStream,
  uploadDocument
} from "./api.js";

const MODES = ["auto", "llm", "rag", "agent"];
const TABS = ["Answer", "Context", "Trace", "Agent Steps", "Metrics"];

function createSessionId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `session-${Date.now()}`;
}

export default function App() {
  const navigate = useNavigate();
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("copilot.sessionId");
    if (existing) return existing;
    const created = createSessionId();
    localStorage.setItem("copilot.sessionId", created);
    return created;
  });
  const [userEmail, setUserEmail] = useState(
    () => localStorage.getItem("userEmail") || ""
  );
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

  useEffect(() => {
    if (!userEmail) {
      getMe()
        .then((data) => {
          setUserEmail(data.email || "");
          localStorage.setItem("userEmail", data.email || "");
        })
        .catch(() => {
          localStorage.removeItem("token");
          localStorage.removeItem("userEmail");
          navigate("/login", { replace: true });
        });
    }
  }, [userEmail, navigate]);

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("userEmail");
    navigate("/login", { replace: true });
  }

  const selectedMetrics = response?.metrics || {};
  const citations = response?.citations || [];
  const chunks = response?.retrieved_chunks || [];
  const agentSteps = response?.agent_steps || [];
  const trace = response?.trace || [];

  useEffect(() => {
    refreshSideData();
  }, [sessionId]);

  async function refreshSideData() {
    try {
      const [historyPayload, docsPayload, metricsPayload, sessionMetricsPayload] =
        await Promise.all([
          getHistory(sessionId),
          listDocuments(sessionId),
          getMetrics(),
          getSessionMetrics(sessionId)
        ]);
      setHistory(historyPayload.turns || []);
      setDocuments(docsPayload || []);
      setMetricsSnapshot(metricsPayload || null);
      setSessionMetrics(sessionMetricsPayload || null);
    } catch {
      setMetricsSnapshot(null);
      setSessionMetrics(null);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await submitQuery();
  }

  async function submitQuery() {
    if (!query.trim() || isQuerying) return;
    setIsQuerying(true);
    setError("");
    setActiveTab("Answer");
    const payload = {
      query: query.trim(),
      session_id: sessionId,
      mode
    };
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
    try {
      await queryCopilotStream(
        payload,
        (token) => {
          setResponse((current) => ({
            ...(current || {}),
            answer: `${current?.answer || ""}${token}`
          }));
        },
        (finalResponse) => {
          setResponse(finalResponse);
          if (finalResponse?.error) {
            setError(finalResponse.answer || "Temporary issue, retrying...");
          }
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
        setResponse(fallback);
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
        `${payload.file_name}: ${payload.chunks_indexed} indexed, ${payload.chunks_skipped} skipped`
      );
      setSuggestedQueries(payload.suggested_queries || []);
      await refreshSideData();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  const routeBadge = useMemo(() => {
    if (!response) return "idle";
    return `${response.mode_used} / ${selectedMetrics.route_decision || "route"}`;
  }, [response, selectedMetrics.route_decision]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <section className="brand-block">
          <div>
            <h1>AI Copilot Console</h1>
            <p>{routeBadge}</p>
          </div>
          {userEmail && (
            <div className="user-block">
              <span className="user-email">{userEmail}</span>
              <button className="logout-button" onClick={handleLogout} title="Sign out">
                <LogOut size={16} />
              </button>
            </div>
          )}
        </section>

        <section className="panel">
          <header className="panel-header">
            <History size={18} aria-hidden="true" />
            <h2>Session</h2>
          </header>
          <code className="session-id">{sessionId}</code>
          <div className="history-list">
            {history.length === 0 ? (
              <p className="empty-state">No turns recorded.</p>
            ) : (
              history.slice(-8).map((turn) => (
                <button
                  className="history-item"
                  key={turn.id}
                  type="button"
                  onClick={() =>
                    setResponse({
                      answer: turn.system_response,
                      session_id: turn.session_id,
                      mode_used: turn.mode_used,
                      citations: turn.metadata?.citations || [],
                      retrieved_chunks: [],
                      agent_steps: [],
                      trace: turn.metadata?.trace || [],
                      metrics: turn.metadata?.metrics || {},
                      request_id: turn.request_id
                    })
                  }
                >
                  <span>{turn.mode_used}</span>
                  <strong>{turn.user_input}</strong>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="panel">
          <header className="panel-header">
            <Database size={18} aria-hidden="true" />
            <h2>Knowledge</h2>
          </header>
          <label className="upload-button">
            {isUploading ? (
              <Loader2 className="spin" size={18} aria-hidden="true" />
            ) : (
              <Upload size={18} aria-hidden="true" />
            )}
            <span>{isUploading ? "Indexing" : "Upload"}</span>
            <input
              accept=".pdf,.txt,.md,.markdown"
              disabled={isUploading}
              onChange={handleUpload}
              type="file"
            />
          </label>
          {uploadStatus && <p className="status-line">{uploadStatus}</p>}
          <div className="document-list">
            {documents.length === 0 ? (
              <p className="empty-state">No indexed files.</p>
            ) : (
              documents.map((document) => (
                <div className="document-item" key={document.document_id}>
                  <FileText size={16} aria-hidden="true" />
                  <div>
                    <strong>{document.file_name}</strong>
                    <span>{document.chunks} chunks</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <form className="composer" onSubmit={handleSubmit}>
          <div className="mode-switch" aria-label="Query mode">
            {MODES.map((item) => (
              <button
                className={mode === item ? "active" : ""}
                key={item}
                onClick={() => setMode(item)}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
          <div className="toggle-row" aria-label="Display options">
            <label>
              <input
                checked={showSources}
                onChange={(event) => setShowSources(event.target.checked)}
                type="checkbox"
              />
              <span>Show sources</span>
            </label>
            <label>
              <input
                checked={showTrace}
                onChange={(event) => setShowTrace(event.target.checked)}
                type="checkbox"
              />
              <span>Show agent trace</span>
            </label>
          </div>
          <div className="query-row">
            <textarea
              aria-label="Query"
              onKeyDown={handleQueryKeyDown}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ask for a grounded answer, retrieval, or agent analysis"
              value={query}
            />
            <button className="send-button" disabled={isQuerying} type="submit">
              {isQuerying ? (
                <Loader2 className="spin" size={20} aria-hidden="true" />
              ) : (
                <Send size={20} aria-hidden="true" />
              )}
              <span>{isQuerying ? "Running" : "Send"}</span>
            </button>
          </div>
          {suggestedQueries.length > 0 && (
            <div className="suggestion-row" aria-label="Suggested queries">
              {suggestedQueries.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  type="button"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </form>

        {error && (
          <div className="error-banner" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <section className="response-shell">
          <nav className="tabs" aria-label="Response sections">
            {TABS.map((tab) => (
              <button
                className={activeTab === tab ? "active" : ""}
                key={tab}
                onClick={() => setActiveTab(tab)}
                type="button"
              >
                {tab}
              </button>
            ))}
          </nav>

          <div className="response-body">
            {activeTab === "Answer" && (
              <AnswerPanel
                answer={response?.answer}
                citations={citations}
                showSources={showSources}
              />
            )}
            {activeTab === "Context" && (
              <ContextPanel chunks={chunks} showSources={showSources} />
            )}
            {activeTab === "Trace" && (
              <TracePanel trace={trace} showTrace={showTrace} />
            )}
            {activeTab === "Agent Steps" && <AgentPanel steps={agentSteps} />}
            {activeTab === "Metrics" && (
              <MetricsPanel
                metrics={selectedMetrics}
                metricsSnapshot={metricsSnapshot}
                sessionMetrics={sessionMetrics}
                requestId={response?.request_id}
              />
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function AnswerPanel({ answer, citations, showSources }) {
  return (
    <div className="answer-panel">
      <article className="answer-text">
        {answer ? <p>{answer}</p> : <p className="empty-state">No answer yet.</p>}
      </article>
      {showSources && citations.length > 0 && (
        <section className="citation-band">
          <h3>Citations</h3>
          <div className="citation-grid">
            {citations.map((citation) => (
              <div className="citation" key={citation.chunk_id}>
                <strong>{citation.source}</strong>
                <span>
                  chunk {citation.chunk_index}
                  {typeof citation.score === "number"
                    ? ` / ${citation.score.toFixed(3)}`
                    : ""}
                </span>
                <p>{citation.quote}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ContextPanel({ chunks, showSources }) {
  if (!showSources) {
    return <p className="empty-state">Sources are hidden.</p>;
  }
  if (chunks.length === 0) {
    return <p className="empty-state">No retrieved context for this turn.</p>;
  }
  return (
    <div className="context-list">
      {chunks.map((chunk) => (
        <article className="context-item" key={chunk.id}>
          <header>
            <strong>{chunk.source}</strong>
            <span>
              chunk {chunk.chunk_index}
              {typeof chunk.score === "number" ? ` / ${chunk.score.toFixed(3)}` : ""}
            </span>
          </header>
          <p>{chunk.text}</p>
        </article>
      ))}
    </div>
  );
}

function TracePanel({ trace, showTrace }) {
  if (!showTrace) {
    return <p className="empty-state">Agent trace is hidden.</p>;
  }
  if (trace.length === 0) {
    return <p className="empty-state">No trace for this turn.</p>;
  }
  return (
    <div className="step-list">
      {trace.map((item, index) => (
        <article className="step-item" key={`${item.step}-${index}`}>
          <header>
            <strong>{index + 1}</strong>
            <span>{item.step}</span>
          </header>
          <pre>{JSON.stringify(item.meta || {}, null, 2)}</pre>
        </article>
      ))}
    </div>
  );
}

function AgentPanel({ steps }) {
  if (steps.length === 0) {
    return <p className="empty-state">No agent steps for this turn.</p>;
  }
  return (
    <div className="step-list">
      {steps.map((step) => (
        <article className="step-item" key={step.step_id}>
          <header>
            <strong>{step.step_id}</strong>
            <span>{step.tool}</span>
            <em>{step.status}</em>
          </header>
          <p>{step.output}</p>
          <small>{Math.round(step.latency_ms)} ms</small>
        </article>
      ))}
    </div>
  );
}

function MetricsPanel({ metrics, metricsSnapshot, sessionMetrics, requestId }) {
  const renderedMetrics =
    typeof metricsSnapshot === "string"
      ? metricsSnapshot
      : JSON.stringify(metricsSnapshot || {}, null, 2);

  return (
    <div className="metrics-grid">
      <Metric label="Latency" value={`${Math.round(metrics.latency_ms || 0)} ms`} />
      <Metric
        label="Retrieval"
        value={`${Math.round(metrics.retrieval_time_ms || 0)} ms`}
      />
      <Metric label="Tokens" value={metrics.tokens || metrics.total_tokens || 0} />
      <Metric label="Prompt" value={metrics.prompt_tokens || 0} />
      <Metric label="Completion" value={metrics.completion_tokens || 0} />
      <Metric label="Total" value={metrics.total_tokens || 0} />
      <Metric label="Cost" value={metrics.cost ?? "n/a"} />
      <Metric label="Session Tokens" value={sessionMetrics?.total_tokens || 0} />
      <Metric label="Session Cost" value={sessionMetrics?.total_cost ?? 0} />
      <Metric label="Cache" value={metrics.cache_hit ? "hit" : "miss"} />
      <Metric label="Provider" value={metrics.provider || "n/a"} />
      <Metric label="Fallback" value={metrics.fallback_used ? "yes" : "no"} />
      <Metric label="Request" value={requestId || "n/a"} wide />
      <Metric label="Route" value={metrics.route_decision || "n/a"} wide />
      <pre className="metrics-text">
        {renderedMetrics === "{}" ? "No metrics collected." : renderedMetrics}
      </pre>
    </div>
  );
}

function Metric({ label, value, wide = false }) {
  return (
    <div className={wide ? "metric wide" : "metric"}>
      <span>{label}</span>
      <strong>{String(value)}</strong>
    </div>
  );
}
