import TokenAnalytics from "./TokenAnalytics";

/*
 * MetricsCard — the Metrics tab. Now a full Token Analytics dashboard on top,
 * with the developer-oriented execution facts kept as a compact strip below.
 */
export default function MetricsCard({ metricsSnapshot, sessionMetrics, chunks = [] }) {
  const m = metricsSnapshot || {};
  const latency = Math.round(m.latency_ms ?? m.latencyMs ?? 0);
  const cacheHit = m.cache_hit ?? m.cacheHit;
  const clientHit = m.client_cache_hit;
  const clientAt = m.client_cache_hit_at;
  const provider = m.provider || "—";
  const model = m.model || "—";
  const retrievalCount =
    m.retrieval_chunk_count ?? m.retrievalChunkCount ?? m.retrieval_count;
  const agentSteps = m.agent_step_count ?? m.agentStepCount ?? m.agent_steps_count;

  const hasAny =
    Object.keys(m).length > 0 ||
    (sessionMetrics &&
      (sessionMetrics.query_count > 0 || sessionMetrics.total_tokens > 0));

  if (!hasAny && !m.latency_ms && !clientHit) {
    return (
      <div className="metrics-empty empty-state-block">
        <p>No metrics for this turn yet.</p>
        <p className="hint">Run a query to see token usage, latency, and cache status.</p>
      </div>
    );
  }

  return (
    <div className="metrics-tab-layout">
      <TokenAnalytics metrics={m} sessionMetrics={sessionMetrics} chunks={chunks} />

      {/* Developer execution strip */}
      <div className="dev-strip glass-panel">
        <div className="dev-strip__row">
          <span className="dev-strip__k">Latency</span>
          <span className="dev-strip__v metric-mono">{latency} ms</span>
        </div>
        <div className="dev-strip__row">
          <span className="dev-strip__k">Provider · Model</span>
          <span className="dev-strip__v metric-mono">{provider} · {model}</span>
        </div>
        <div className="dev-strip__row">
          <span className="dev-strip__k">Server cache</span>
          <span className="dev-strip__v">
            {cacheHit ? <span className="badge green">Hit</span> : <span className="badge muted">Miss</span>}
          </span>
        </div>
        <div className="dev-strip__row">
          <span className="dev-strip__k">Client cache</span>
          <span className="dev-strip__v">
            {clientHit ? (
              <>
                <span className="badge blue">Hit</span>
                {clientAt && <small className="cache-ts">{clientAt}</small>}
              </>
            ) : (
              <span className="badge muted">Miss</span>
            )}
          </span>
        </div>
        <div className="dev-strip__row">
          <span className="dev-strip__k">Retrieval chunks</span>
          <span className="dev-strip__v metric-mono">{retrievalCount ?? "—"}</span>
        </div>
        <div className="dev-strip__row">
          <span className="dev-strip__k">Agent steps</span>
          <span className="dev-strip__v metric-mono">{agentSteps ?? "—"}</span>
        </div>
      </div>
    </div>
  );
}
