import { useMemo } from "react";
import {
  Send,
  Search,
  History,
  Wrench,
  Cpu,
  Zap,
  Check,
  Loader2,
  X,
  Minus,
  Workflow
} from "lucide-react";

/*
 * PipelineRail — live, glass-box visualization of what the AI is doing.
 *
 * It maps 1:1 onto data the backend already returns:
 *   - mode ...................... which stages are even applicable (llm skips retrieval/tools)
 *   - response.trace[] .......... per-stage durations (meta.latency_ms)
 *   - response.retrieved_chunks / metrics.retrieval_chunk_count .. Context node
 *   - response.agent_steps[] / metrics.agent_step_count ......... Tools node
 *   - response.metrics .......... model/provider + final timings
 *   - isQuerying / answer length  drive the live "active" states before finalize
 *
 * It never surfaces hidden reasoning — only stage, count, and duration.
 */

const STAGES = [
  { key: "prompt", label: "Prompt", hue: "var(--hue-prompt)", icon: Send },
  { key: "context", label: "Context", hue: "var(--hue-context)", icon: Search },
  { key: "memory", label: "Memory", hue: "var(--hue-memory)", icon: History },
  { key: "tools", label: "Tools", hue: "var(--hue-tools)", icon: Wrench },
  { key: "model", label: "Model", hue: "var(--hue-model)", icon: Cpu },
  { key: "stream", label: "Stream", hue: "var(--hue-stream)", icon: Zap }
];

function ms(v) {
  return v == null ? "" : `${Math.round(v)}ms`;
}

// Find the latency of a trace step whose name loosely matches any keyword.
function traceLatency(trace, keywords) {
  for (const item of trace || []) {
    const name = String(item.step || "").toLowerCase();
    if (keywords.some((k) => name.includes(k))) {
      return item.meta?.latency_ms ?? null;
    }
  }
  return null;
}

function deriveStages({ response, mode, isQuerying, hasCompletedTurn }) {
  const trace = response?.trace || [];
  const metrics = response?.metrics || {};
  const answer = response?.answer || "";
  const streaming = isQuerying && answer.length > 0;

  const chunkCount =
    metrics.retrieval_chunk_count ??
    metrics.retrievalChunkCount ??
    response?.retrieved_chunks?.length ??
    0;
  const stepCount =
    metrics.agent_step_count ??
    metrics.agentStepCount ??
    response?.agent_steps?.length ??
    0;

  const usesRetrieval = mode === "rag" || mode === "agent" || chunkCount > 0;
  const usesTools = mode === "agent" || stepCount > 0;

  // Default statuses depend on lifecycle phase.
  // Phase A: querying, no tokens yet  -> upstream stages "done", model "active".
  // Phase B: streaming tokens          -> model "done", stream "active".
  // Phase C: finalized                 -> everything reconciled to real data.
  const status = {};

  if (hasCompletedTurn && !isQuerying) {
    status.prompt = "done";
    status.context = usesRetrieval ? "done" : "skipped";
    status.memory = "done";
    status.tools = usesTools ? "done" : "skipped";
    status.model = "done";
    status.stream = "done";
    if (response?.error) status.model = "error";
  } else if (isQuerying) {
    status.prompt = "done";
    status.context = usesRetrieval ? (streaming ? "done" : "active") : "skipped";
    status.memory = "done";
    status.tools = usesTools ? "done" : "skipped";
    status.model = streaming ? "done" : "active";
    status.stream = streaming ? "active" : "pending";
    // If retrieval is still running (no tokens, RAG/agent), front-run Context.
    if (usesRetrieval && !streaming) {
      status.context = "active";
      status.model = "pending";
    }
  } else {
    // Idle with a prior response in view.
    status.prompt = "done";
    status.context = usesRetrieval ? "done" : "skipped";
    status.memory = "done";
    status.tools = usesTools ? "done" : "skipped";
    status.model = "done";
    status.stream = "done";
  }

  const detail = {
    prompt: "received",
    context: usesRetrieval ? `${chunkCount} chunk${chunkCount === 1 ? "" : "s"}` : "n/a",
    memory: ms(traceLatency(trace, ["memory", "history"])) || "loaded",
    tools: usesTools ? `${stepCount} step${stepCount === 1 ? "" : "s"}` : "n/a",
    model: metrics.model ? String(metrics.model).split("/").pop() : "processing",
    stream: streaming
      ? "streaming…"
      : hasCompletedTurn
      ? ms(metrics.latency_ms ?? metrics.latencyMs)
      : "output"
  };

  // Prefer real trace latencies for context/model when available.
  const ctxLat = traceLatency(trace, ["retriev", "context", "search"]);
  if (usesRetrieval && ctxLat != null && status.context === "done") {
    detail.context = `${chunkCount} · ${ms(ctxLat)}`;
  }

  return STAGES.map((s) => ({ ...s, status: status[s.key], detail: detail[s.key] }));
}

function StatusGlyph({ status }) {
  if (status === "done") return <Check size={12} className="st-done" strokeWidth={3} />;
  if (status === "active") return <Loader2 size={12} className="st-active spin" />;
  if (status === "error") return <X size={12} className="st-error" strokeWidth={3} />;
  if (status === "skipped") return <Minus size={12} className="st-skip" />;
  return null;
}

export default function PipelineRail({ response, mode, isQuerying, hasCompletedTurn }) {
  const stages = useMemo(
    () => deriveStages({ response, mode, isQuerying, hasCompletedTurn }),
    [response, mode, isQuerying, hasCompletedTurn]
  );

  // Only show once there's something to narrate.
  if (!isQuerying && !hasCompletedTurn) return null;

  const metrics = response?.metrics || {};
  const doneCount = stages.filter((s) => s.status === "done").length;
  const activeCount = stages.filter((s) => s.status === "active").length;
  const totalLatency = metrics.latency_ms ?? metrics.latencyMs;
  const progress = Math.round(
    ((doneCount + activeCount * 0.55) / Math.max(1, stages.length)) * 100
  );

  const summary = isQuerying
    ? activeCount > 0
      ? "running…"
      : "starting…"
    : `${doneCount} stage${doneCount === 1 ? "" : "s"}${
        totalLatency != null ? ` · ${Math.round(totalLatency)}ms` : ""
      }`;

  return (
    <section
      className="pipeline-rail glass-panel"
      aria-label="AI processing pipeline"
      aria-live="polite"
      style={{ "--pipeline-progress": `${progress}%` }}
    >
      <div className="pipeline-rail__head">
        <span className="pipeline-rail__title">
          <Workflow size={13} aria-hidden />
          AI Pipeline
        </span>
        <span className="pipeline-rail__summary">{summary}</span>
      </div>

      <div className="pipeline-rail__flow" aria-hidden>
        <span className="pipeline-rail__flow-fill" />
      </div>

      <div className="pipeline-rail__track" role="list">
        {stages.map((s) => {
          const Icon = s.icon;
          const active = s.status === "active";
          return (
            <div
              key={s.key}
              role="listitem"
              className={`pnode is-${s.status}`}
              style={{ "--stage-hue": s.hue }}
              title={`${s.label}: ${s.status}${s.detail ? ` — ${s.detail}` : ""}`}
              aria-label={`${s.label} stage, ${s.status}${s.detail ? `, ${s.detail}` : ""}`}
            >
              <span className="pnode__status">
                <StatusGlyph status={s.status} />
              </span>
              <span className="pnode__icon">
                <Icon size={16} className={active ? "" : ""} aria-hidden />
              </span>
              <span className="pnode__label">{s.label}</span>
              <span className="pnode__detail">{s.detail}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
