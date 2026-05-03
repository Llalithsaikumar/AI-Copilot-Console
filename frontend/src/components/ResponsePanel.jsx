import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BookOpen,
  CheckCircle2,
  Clock,
  FileText,
  GitBranch,
  LineChart,
  XCircle
} from "lucide-react";
import MetricsCard from "./MetricsCard";

const TABS = ["Answer", "Context", "Trace", "Agent Steps", "Metrics"];

function EmptyIcon({ title, body, icon: Icon }) {
  return (
    <div className="empty-state-block tab-empty">
      <Icon size={40} className="empty-icon" aria-hidden />
      <p className="empty-title">{title}</p>
      <p className="hint">{body}</p>
    </div>
  );
}

function stepVisualStatus(status) {
  const s = String(status || "").toLowerCase();
  if (s === "ok" || s === "done") return "done";
  if (s === "running") return "running";
  if (s === "error" || s === "failed") return "failed";
  return "done";
}

export default function ResponsePanel({
  response,
  activeTab,
  setActiveTab,
  showSources,
  showTrace,
  isQuerying,
  metricsSnapshot,
  sessionMetrics,
  hasCompletedTurn
}) {
  const citations = response?.citations || [];
  const chunks = response?.retrieved_chunks || [];
  const agentSteps = response?.agent_steps || [];
  const trace = response?.trace || [];

  const showIdleEmpty = !hasCompletedTurn && !isQuerying;

  return (
    <div className="response-panel glass-panel">
      <div className="response-tabs">
        {TABS.map((tab) => {
          const isActive = activeTab === tab;
          let hasContent = false;
          if (tab === "Context" && chunks.length > 0) hasContent = true;
          if (tab === "Trace" && trace.length > 0) hasContent = true;
          if (tab === "Agent Steps" && agentSteps.length > 0) hasContent = true;

          return (
            <button
              key={tab}
              type="button"
              className={`tab-btn ${isActive ? "active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
              {hasContent && <span className="unread-dot"></span>}
              {isActive && <div className="active-underline" />}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        {activeTab === "Answer" && (
          <div className="answer-tab">
            {isQuerying && !response?.answer ? (
              <div className="skeleton-loader">
                <div className="skeleton-line full"></div>
                <div className="skeleton-line three-quarter"></div>
                <div className="skeleton-line half"></div>
              </div>
            ) : response?.answer ? (
              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{response.answer}</ReactMarkdown>
              </div>
            ) : showIdleEmpty ? (
              <EmptyIcon
                icon={BookOpen}
                title="No answer yet"
                body="Submit a query to stream a markdown answer here."
              />
            ) : (
              <p className="empty-state">No answer yet.</p>
            )}

            {showSources && citations.length > 0 && (
              <div className="citations-section">
                <h3>Sources</h3>
                <div className="citations-list">
                  {citations.map((c, i) => (
                    <span key={i} className="citation-chip">
                      <FileText size={12} />
                      [{c.chunk_index}] {c.source}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "Context" && (
          <div className="context-tab">
            {showIdleEmpty ? (
              <EmptyIcon
                icon={FileText}
                title="No context yet"
                body="Retrieved chunks from your knowledge base appear here in RAG mode."
              />
            ) : !showSources ? (
              <p className="empty-state">Sources are hidden.</p>
            ) : chunks.length === 0 ? (
              <EmptyIcon
                icon={FileText}
                title="No retrieved chunks"
                body="Try RAG or Agent mode, or upload documents to index."
              />
            ) : (
              <div className="context-cards">
                {chunks.map((chunk) => {
                  const score =
                    typeof chunk.score === "number"
                      ? Math.min(1, Math.max(0, chunk.score))
                      : 0;
                  return (
                    <div className="context-card glass-panel" key={chunk.id}>
                      <div className="context-header">
                        <strong>{chunk.source}</strong>
                        <span className="badge violet">Chunk {chunk.chunk_index}</span>
                      </div>
                      <div className="score-bar-wrap">
                        <div className="score-bar">
                          <div
                            className="score-fill"
                            style={{ width: `${score * 100}%` }}
                          />
                        </div>
                        <span className="score-label">{score.toFixed(3)}</span>
                      </div>
                      <p className="context-text">{chunk.text}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === "Trace" && (
          <div className="trace-tab">
            {showIdleEmpty ? (
              <EmptyIcon
                icon={GitBranch}
                title="No trace yet"
                body="Execution steps and timings are recorded after each query."
              />
            ) : !showTrace ? (
              <p className="empty-state">Trace is hidden.</p>
            ) : trace.length === 0 ? (
              <EmptyIcon
                icon={GitBranch}
                title="Empty trace"
                body="This response did not include trace steps."
              />
            ) : (
              <div className="timeline">
                {trace.map((item, index) => (
                  <div className="timeline-item" key={index}>
                    <div className="timeline-dot"></div>
                    <div className="timeline-content glass-panel">
                      <div className="timeline-head">
                        <strong>{item.step}</strong>
                        <time className="trace-time">
                          {item.meta?.latency_ms != null
                            ? `${Math.round(item.meta.latency_ms)} ms`
                            : ""}
                        </time>
                      </div>
                      <pre className="trace-meta">{JSON.stringify(item.meta || {}, null, 2)}</pre>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "Agent Steps" && (
          <div className="agent-steps-tab">
            {showIdleEmpty ? (
              <EmptyIcon
                icon={LineChart}
                title="No agent run yet"
                body="Agent mode shows planner–executor tool steps here."
              />
            ) : agentSteps.length === 0 ? (
              <EmptyIcon
                icon={LineChart}
                title="No agent steps"
                body="Use Agent mode for multi-step tool usage."
              />
            ) : (
              <div className="pipeline">
                {agentSteps.map((step, index) => {
                  const vis = stepVisualStatus(step.status);
                  return (
                    <div className="pipeline-step glass-panel" key={step.step_id || index}>
                      <div className="step-header">
                        <span className="step-number">{index + 1}</span>
                        <strong>{step.tool}</strong>
                        <span className={`status-icon ${vis}`}>
                          {vis === "done" && <CheckCircle2 size={16} className="accent-teal" />}
                          {vis === "running" && <Clock size={16} className="accent-blue spin" />}
                          {vis === "failed" && <XCircle size={16} className="danger" />}
                        </span>
                      </div>
                      <p className="step-output">{step.output}</p>
                      <small>{Math.round(step.latency_ms)} ms</small>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === "Metrics" && (
          <MetricsCard metricsSnapshot={metricsSnapshot} sessionMetrics={sessionMetrics} />
        )}
      </div>
    </div>
  );
}
