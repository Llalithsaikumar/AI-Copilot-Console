import {
  FileText,
  GitBranch,
  LineChart,
  ChevronRight,
  CheckCircle2,
  Clock,
  XCircle
} from "lucide-react";
import MetricsCard from "./MetricsCard";

/*
 * AssistantDetails — the per-message "glass box". Everything the old global
 * tabbed panel used to show (Context / Trace / Agent Steps / Metrics) now lives
 * here as collapsible sections, rendered only when that message carries data.
 * Keeps the chat surface clean while preserving every console detail.
 */

function stepVisualStatus(status) {
  const s = String(status || "").toLowerCase();
  if (s === "ok" || s === "done") return "done";
  if (s === "running") return "running";
  if (s === "error" || s === "failed") return "failed";
  return "done";
}

function Section({ icon: Icon, title, count, children, defaultOpen = false }) {
  return (
    <details className="detail-section" open={defaultOpen}>
      <summary className="detail-summary">
        <ChevronRight size={14} className="detail-caret" aria-hidden />
        <Icon size={14} aria-hidden />
        <span className="detail-title">{title}</span>
        {count != null && <span className="detail-count">{count}</span>}
      </summary>
      <div className="detail-body">{children}</div>
    </details>
  );
}

export default function AssistantDetails({
  message,
  showTrace,
  sessionMetrics
}) {
  const chunks = message?.chunks || [];
  const trace = message?.trace || [];
  const agentSteps = message?.agentSteps || [];
  const metrics = message?.metrics || {};
  const hasMetrics = Object.keys(metrics).length > 0;

  const hasAnything =
    chunks.length > 0 || trace.length > 0 || agentSteps.length > 0 || hasMetrics;
  if (!hasAnything) return null;

  return (
    <div className="assistant-details">
      {chunks.length > 0 && (
        <Section icon={FileText} title="Context" count={chunks.length}>
          <div className="context-cards">
            {chunks.map((chunk) => {
              const score =
                typeof chunk.score === "number"
                  ? Math.min(1, Math.max(0, chunk.score))
                  : 0;
              return (
                <div className="context-card" key={chunk.id}>
                  <div className="context-header">
                    <strong>{chunk.source}</strong>
                    <span className="badge violet">Chunk {chunk.chunk_index}</span>
                  </div>
                  <div className="score-bar-wrap">
                    <div className="score-bar">
                      <div className="score-fill" style={{ width: `${score * 100}%` }} />
                    </div>
                    <span className="score-label">{score.toFixed(3)}</span>
                  </div>
                  <p className="context-text">{chunk.text}</p>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {trace.length > 0 &&
        (showTrace ? (
          <Section icon={GitBranch} title="Trace" count={trace.length}>
            <div className="timeline">
              {trace.map((item, index) => (
                <div className="timeline-item" key={index}>
                  <div className="timeline-dot" />
                  <div className="timeline-content">
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
          </Section>
        ) : (
          <p className="empty-state">Trace is hidden.</p>
        ))}

      {agentSteps.length > 0 && (
        <Section icon={LineChart} title="Agent Steps" count={agentSteps.length}>
          <div className="pipeline">
            {agentSteps.map((step, index) => {
              const vis = stepVisualStatus(step.status);
              return (
                <div className="pipeline-step" key={step.step_id || index}>
                  <div className="step-header">
                    <span className="step-number">{index + 1}</span>
                    <strong>{step.tool}</strong>
                    <span className={`status-icon ${vis}`}>
                      {vis === "done" && <CheckCircle2 size={16} className="accent" />}
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
        </Section>
      )}

      {hasMetrics && (
        <Section icon={LineChart} title="Metrics" defaultOpen>
          <MetricsCard metricsSnapshot={metrics} sessionMetrics={sessionMetrics} chunks={chunks} />
        </Section>
      )}
    </div>
  );
}
