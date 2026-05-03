import { useState } from "react";
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
  Eraser
} from "lucide-react";

export default function Sidebar({
  collapsed,
  setCollapsed,
  sessionId,
  sessions,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  history,
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
  const [sessionOpen, setSessionOpen] = useState(true);
  const [filesOpen, setFilesOpen] = useState(true);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const asideClass = `sidebar ${collapsed ? "collapsed" : ""}`;

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
            <div>
              <h1>Copilot</h1>
              <div className="live-status">
                <span className="pulse-dot"></span>
                Live · {routeBadge}
              </div>
            </div>
          </section>

          <div className="divider"></div>

          <section className="panel">
            <header
              className="panel-header"
              onClick={() => setSessionOpen(!sessionOpen)}
              style={{ cursor: "pointer" }}
            >
              <div className="panel-title">
                <History size={16} />
                <h2>Sessions</h2>
              </div>
              <div className="panel-actions">
                <button
                  type="button"
                  className="btn tiny ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onNewSession?.();
                  }}
                >
                  New
                </button>
                <div className="badge violet">{history.length} turns</div>
              </div>
            </header>

            {sessionOpen && (
              <div className="panel-content">
                <div className="session-list">
                  {(sessions || []).map((s) => (
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
                          {(s.last_query_preview || "Empty session").slice(0, 42)}
                          {(s.last_query_preview || "").length > 42 ? "…" : ""}
                        </span>
                        <span className="session-meta">
                          <Clock size={12} /> {s.turn_count ?? 0} ·{" "}
                          {(s.last_active_at || "").replace("T", " ").slice(0, 16)}
                        </span>
                      </button>
                      <button
                        type="button"
                        className="icon-btn danger"
                        title="Delete session"
                        onClick={() => onDeleteSession?.(s.session_id)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="session-chip">
                  <code title={sessionId}>{sessionId.slice(0, 22)}…</code>
                  <button onClick={copyToClipboard} title="Copy session id" className="icon-btn">
                    {copied ? <CheckCircle2 size={14} className="accent-teal" /> : <Copy size={14} />}
                  </button>
                </div>

                <div className="history-list">
                  {history.length === 0 ? (
                    <p className="empty-state">No turns in this session.</p>
                  ) : (
                    history.slice(-12).map((turn) => (
                      <button
                        className="history-item"
                        key={turn.id}
                        title={
                          turn.metadata?.metrics
                            ? `Tokens: ${turn.metadata.metrics.total_tokens ?? "—"} · Latency: ${Math.round(turn.metadata.metrics.latency_ms ?? 0)} ms`
                            : ""
                        }
                        onClick={() =>
                          setResponse({
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
                    ))
                  )}
                </div>

                <div className="cache-actions">
                  <button type="button" className="btn tiny ghost" onClick={onClearSessionCache}>
                    <Eraser size={14} /> Clear query cache (session)
                  </button>
                  <button type="button" className="btn tiny ghost" onClick={onClearAllCache}>
                    <Eraser size={14} /> Clear all cached queries
                  </button>
                </div>
              </div>
            )}
          </section>

          <div className="divider"></div>

          <section className="panel flex-grow">
            <header
              className="panel-header"
              onClick={() => setFilesOpen(!filesOpen)}
              style={{ cursor: "pointer" }}
            >
              <div className="panel-title">
                <FolderOpen size={16} />
                <h2>Files</h2>
              </div>
            </header>

            {filesOpen && (
              <>
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
                  <span>{isUploading ? "Indexing…" : "Upload document"}</span>
                  <small>PDF, TXT, MD</small>
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
              </>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
