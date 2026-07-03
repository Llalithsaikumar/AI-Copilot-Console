import { useMemo, useState } from "react";
import {
  Database,
  History,
  Upload,
  Loader2,
  FileText,
  Trash2,
  Copy,
  CheckCircle2,
  PanelLeftClose,
  PanelLeft,
  FolderOpen,
  Clock,
  Eraser,
  Search,
  Pin,
  Plus,
  Sparkles,
  ChevronDown
} from "lucide-react";
import { readPinnedSet, togglePinned } from "../lib/accountStorage.js";

const MODE_HUE = {
  auto: "var(--accent)",
  llm: "var(--hue-prompt)",
  rag: "var(--hue-context)",
  agent: "var(--hue-tools)"
};

const GROUP_ORDER = ["Today", "Yesterday", "Previous 7 days", "Earlier"];

function bucketFor(iso) {
  if (!iso) return "Earlier";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Earlier";
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startYest = new Date(startToday);
  startYest.setDate(startYest.getDate() - 1);
  const start7 = new Date(startToday);
  start7.setDate(start7.getDate() - 7);
  if (d >= startToday) return "Today";
  if (d >= startYest) return "Yesterday";
  if (d >= start7) return "Previous 7 days";
  return "Earlier";
}

export default function Sidebar({
  collapsed,
  setCollapsed,
  accountId,
  sessionId,
  sessions,
  sessionMetrics,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  history = [],
  documents,
  routeBadge,
  isUploading,
  handleUpload,
  uploadStatus,
  setResponse,
  onDeleteFile,
  onClearSessionCache,
  onClearAllCache
}) {
  const [copied, setCopied] = useState(false);
  const [filesOpen, setFilesOpen] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all"); // all | pinned | agent | rag
  const [pinTick, setPinTick] = useState(0);

  const pinned = useMemo(
    () => (accountId ? readPinnedSet(accountId) : new Set()),
    [accountId, pinTick]
  );

  const copyToClipboard = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTogglePin = (id, e) => {
    e.stopPropagation();
    if (!accountId) return;
    togglePinned(accountId, id);
    setPinTick((t) => t + 1);
  };

  // Filter → group sessions.
  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    const out = { Pinned: [], Today: [], Yesterday: [], "Previous 7 days": [], Earlier: [] };
    for (const s of sessions || []) {
      const preview = (s.last_query_preview || "").toLowerCase();
      const mode = (s.mode || "").toLowerCase();
      if (q && !preview.includes(q)) continue;
      if (filter === "pinned" && !pinned.has(s.session_id)) continue;
      if (filter === "agent" && mode !== "agent") continue;
      if (filter === "rag" && mode !== "rag") continue;
      if (pinned.has(s.session_id)) out.Pinned.push(s);
      else out[bucketFor(s.last_active_at)].push(s);
    }
    return out;
  }, [sessions, search, filter, pinned]);

  const renderRow = (s) => {
    const isPinned = pinned.has(s.session_id);
    const hue = MODE_HUE[s.mode] || "var(--fg-subtle)";
    return (
      <div
        key={s.session_id}
        className={`session-row ${sessionId === s.session_id ? "active" : ""}`}
      >
        <button
          type="button"
          className="session-row-main"
          onClick={() => onSelectSession?.(s.session_id)}
        >
          <span className="session-preview">
            <i className="mode-dot" style={{ background: hue }} aria-hidden />
            {(s.last_query_preview || "Empty session").slice(0, 40)}
            {(s.last_query_preview || "").length > 40 ? "…" : ""}
          </span>
          <span className="session-meta">
            <Clock size={11} /> {s.turn_count ?? 0} ·{" "}
            {(s.last_active_at || "").replace("T", " ").slice(0, 16)}
          </span>
        </button>
        <button
          type="button"
          className={`icon-btn ${isPinned ? "is-pinned" : ""}`}
          title={isPinned ? "Unpin" : "Pin"}
          onClick={(e) => handleTogglePin(s.session_id, e)}
        >
          <Pin size={13} fill={isPinned ? "currentColor" : "none"} />
        </button>
        <button
          type="button"
          className="icon-btn danger"
          title="Delete session"
          onClick={() => onDeleteSession?.(s.session_id)}
        >
          <Trash2 size={13} />
        </button>
      </div>
    );
  };

  const asideClass = `sidebar ${collapsed ? "collapsed" : ""}`;
  const visibleOrder = filter === "pinned" ? ["Pinned"] : ["Pinned", ...GROUP_ORDER];
  const hasAnySession = visibleOrder.some((g) => groups[g].length > 0);

  return (
    <aside className={asideClass}>
      <button
        type="button"
        className="sidebar-collapse-toggle"
        onClick={() => setCollapsed(!collapsed)}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
      </button>

      {!collapsed && (
        <>
          <section className="brand-block compact-brand">
            <div className="sidebar-brand-mark" aria-hidden>
              <Sparkles size={18} />
            </div>
            <div className="sidebar-brand-copy">
              <h1>Copilot</h1>
              <div className="live-status">
                <span className="pulse-dot"></span>
                <span>Live</span>
                <span className="route-chip">{routeBadge}</span>
              </div>
            </div>
          </section>

          <div className="sidebar-scroll">
            <section className="panel sidebar-panel sidebar-panel--chats">
              <button type="button" className="btn primary new-chat-btn" onClick={() => onNewSession?.()}>
                <Plus size={15} /> New chat
              </button>

              <div className="sidebar-search">
                <Search size={14} className="sidebar-search__icon" aria-hidden />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search chats…"
                  aria-label="Search conversations"
                />
              </div>

              <div className="filter-chips" role="tablist" aria-label="Conversation filters">
                {["all", "pinned", "agent", "rag"].map((f) => (
                  <button
                    key={f}
                    type="button"
                    role="tab"
                    aria-selected={filter === f}
                    className={`filter-chip ${filter === f ? "active" : ""}`}
                    onClick={() => setFilter(f)}
                  >
                    {f === "all" ? "All" : f === "pinned" ? "Pinned" : f.toUpperCase()}
                  </button>
                ))}
              </div>

              {/* Session footprint */}
              {sessionMetrics && sessionMetrics.query_count > 0 && (
                <div className="footprint glass-panel">
                  <div className="footprint__stat">
                    <span className="footprint__v">{sessionMetrics.query_count}</span>
                    <span className="footprint__k">queries</span>
                  </div>
                  <div className="footprint__stat">
                    <span className="footprint__v">
                      {(sessionMetrics.total_tokens || 0).toLocaleString()}
                    </span>
                    <span className="footprint__k">tokens</span>
                  </div>
                  <div className="footprint__stat">
                    <span className="footprint__v">
                      {Math.round(sessionMetrics.avg_latency_ms || 0)}ms
                    </span>
                    <span className="footprint__k">avg</span>
                  </div>
                </div>
              )}

              <div className="session-groups">
                {!hasAnySession ? (
                  <p className="empty-state">No conversations match.</p>
                ) : (
                  visibleOrder.map((g) =>
                    groups[g].length ? (
                      <div className="session-group" key={g}>
                        <div className="session-group__label">
                          {g === "Pinned" && <Pin size={11} />}
                          {g}
                        </div>
                        <div className="session-list">{groups[g].map(renderRow)}</div>
                      </div>
                    ) : null
                  )
                )}
              </div>

              {history.length > 0 && (
                <div className="session-turns">
                  <div className="session-group__label">
                    <History size={11} /> This session · {history.length} turns
                  </div>
                  <div className="history-list">
                    {history.slice(-8).map((turn) => (
                      <button
                        className="history-item"
                        key={turn.id}
                        title={
                          turn.metadata?.metrics
                            ? `Tokens: ${turn.metadata.metrics.total_tokens ?? "—"} · Latency: ${Math.round(turn.metadata.metrics.latency_ms ?? 0)} ms`
                            : ""
                        }
                        onClick={() =>
                          setResponse?.({
                            answer: turn.system_response,
                            session_id: turn.session_id,
                            mode_used: turn.mode_used,
                            citations: turn.metadata?.citations || [],
                            retrieved_chunks: turn.metadata?.retrieved_chunks || [],
                            agent_steps: [],
                            trace: turn.metadata?.trace || [],
                            metrics: turn.metadata?.metrics || {},
                            request_id: turn.request_id
                          })
                        }
                      >
                        <span className="mode-badge">{turn.mode_used}</span>
                        <strong>{turn.user_input}</strong>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="session-chip">
                <code title={sessionId}>{sessionId.slice(0, 22)}…</code>
                <button onClick={copyToClipboard} title="Copy session id" className="icon-btn">
                  {copied ? <CheckCircle2 size={14} className="accent-teal" /> : <Copy size={14} />}
                </button>
              </div>

              <div className="cache-actions">
                <button type="button" className="btn tiny ghost" onClick={onClearSessionCache}>
                  <Eraser size={14} /> Clear query cache (session)
                </button>
                <button type="button" className="btn tiny ghost" onClick={onClearAllCache}>
                  <Eraser size={14} /> Clear all cached queries
                </button>
              </div>
            </section>

            <div className="divider"></div>

            <section className="panel flex-grow sidebar-panel sidebar-panel--knowledge">
              <header
                className={`panel-header knowledge-header ${filesOpen ? "is-open" : ""}`}
                onClick={() => setFilesOpen(!filesOpen)}
                style={{ cursor: "pointer" }}
              >
                <div className="panel-title">
                  <FolderOpen size={16} />
                  <h2>Knowledge</h2>
                </div>
                <div className="knowledge-actions">
                  <div className="badge violet">{documents.length}</div>
                  <ChevronDown size={14} className="knowledge-caret" aria-hidden />
                </div>
              </header>

              {filesOpen && (
                <div className="knowledge-body">
                  <label className="upload-zone">
                    <input
                      aria-label="Upload document"
                      accept=".pdf,.txt,.md,.markdown,.docx"
                      disabled={isUploading}
                      onChange={handleUpload}
                      type="file"
                      className="hidden"
                    />
                    {isUploading ? (
                      <Loader2 className="spin accent-teal" size={24} />
                    ) : (
                      <Upload className="accent-teal" size={24} />
                    )}
                    <span className="upload-copy">
                      <strong>{isUploading ? "Indexing..." : "Upload document"}</strong>
                      <small>PDF, TXT, MD, DOCX</small>
                    </span>
                  </label>
                  {uploadStatus && <p className="status-line">{uploadStatus}</p>}

                  <div className="document-list">
                    {documents.length === 0 ? (
                      <div className="empty-illustration">
                        <Database size={28} />
                        <p>No files indexed.</p>
                      </div>
                    ) : (
                      documents.map((doc) => (
                        <div className="document-item" key={doc.document_id}>
                          <div className="doc-info">
                            <FileText size={16} className="accent-blue" />
                            <div>
                              <strong>{doc.file_name}</strong>
                              <span>
                                {doc.chunks} chunks
                                {doc.chunks_skipped > 0 ? ` · ${doc.chunks_skipped} skipped` : ""}
                              </span>
                              <span className={`file-status status-${doc.status || "indexed"}`}>
                                {doc.status || "indexed"}
                              </span>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="icon-btn danger"
                            title="Delete file"
                            onClick={() => onDeleteFile?.(doc)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </aside>
  );
}
