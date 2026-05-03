export default function MetricsCard({ metricsSnapshot, sessionMetrics }) {
  const m = metricsSnapshot || {};
  const prompt = m.prompt_tokens ?? m.promptTokens ?? 0;
  const completion = m.completion_tokens ?? m.completionTokens ?? 0;
  const total =
    m.total_tokens ??
    m.totalTokens ??
    (Number(prompt) + Number(completion) || m.tokens || 0);
  const latency = Math.round(m.latency_ms ?? m.latencyMs ?? 0);
  const cacheHit = m.cache_hit ?? m.cacheHit;
  const clientHit = m.client_cache_hit;
  const clientAt = m.client_cache_hit_at;
  const model = m.model || "—";
  const provider = m.provider || "—";
  const retrievalCount =
    m.retrieval_chunk_count ?? m.retrievalChunkCount ?? m.retrieval_count;
  const agentSteps =
    m.agent_step_count ?? m.agentStepCount ?? m.agent_steps_count;

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
      <div className="metrics-grid-detailed">
        <div className="metric-tile glass-panel">
          <span className="metric-label">Input tokens</span>
          <span className="metric-value">{prompt}</span>
        </div>
        <div className="metric-tile glass-panel">
          <span className="metric-label">Output tokens</span>
          <span className="metric-value">{completion}</span>
        </div>
        <div className="metric-tile glass-panel">
          <span className="metric-label">Total tokens</span>
          <span className="metric-value">{total}</span>
        </div>
        <div className="metric-tile glass-panel">
          <span className="metric-label">Latency (ms)</span>
          <span className="metric-value">{latency}</span>
        </div>
        <div className="metric-tile glass-panel metric-span-2">
          <span className="metric-label">Cache hit (server)</span>
          <span className="metric-value">
            {cacheHit ? (
              <span className="badge green">Yes</span>
            ) : (
              <span className="badge muted">No</span>
            )}
          </span>
        </div>
        <div className="metric-tile glass-panel metric-span-2">
          <span className="metric-label">Client cache</span>
          <span className="metric-value">
            {clientHit ? (
              <>
                <span className="badge blue">Hit</span>
                <small className="cache-ts">{clientAt || ""}</small>
              </>
            ) : (
              <span className="badge muted">Miss</span>
            )}
          </span>
        </div>
        <div className="metric-tile glass-panel metric-span-2">
          <span className="metric-label">Model</span>
          <span className="metric-value metric-mono">
            {provider} · {model}
          </span>
        </div>
        <div className="metric-tile glass-panel">
          <span className="metric-label">Retrieval chunks</span>
          <span className="metric-value">{retrievalCount ?? "—"}</span>
        </div>
        <div className="metric-tile glass-panel">
          <span className="metric-label">Agent steps</span>
          <span className="metric-value">{agentSteps ?? "—"}</span>
        </div>
      </div>

      {sessionMetrics && sessionMetrics.query_count > 0 && (
        <div className="session-metrics-summary glass-panel">
          <h4>Session aggregate</h4>
          <p>
            Queries: {sessionMetrics.query_count} · Tokens: {sessionMetrics.total_tokens} · Avg
            latency: {Math.round(sessionMetrics.avg_latency_ms)} ms
          </p>
        </div>
      )}
    </div>
  );
}
