import ContextGauge from "./ContextGauge";
import ContextWindowBar from "./ContextWindowBar";
import {
  readTokens,
  contextUsage,
  costFor,
  shortModel
} from "../lib/aiStatus.js";

/*
 * TokenAnalytics — the token dashboard for one turn.
 * Everything derives from the real `metrics` payload; capacity and price are
 * frontend constants (aiStatus.js), clearly placeholder-marked there.
 */

function StatTile({ label, value, sub, accent }) {
  return (
    <div className="tk-tile glass-panel">
      <span className="tk-tile__label">{label}</span>
      <span className="tk-tile__value" style={accent ? { color: accent } : undefined}>
        {value}
      </span>
      {sub && <span className="tk-tile__sub">{sub}</span>}
    </div>
  );
}

export default function TokenAnalytics({ metrics = {}, sessionMetrics, chunks = [] }) {
  const { prompt, completion, total } = readTokens(metrics);
  const { used, capacity, pct } = contextUsage(metrics);
  const cost = costFor(metrics.model, prompt, completion);
  const model = shortModel(metrics.model) || "—";

  const inPct = total > 0 ? (prompt / total) * 100 : 0;
  const outPct = total > 0 ? (completion / total) * 100 : 0;

  const queryCount = sessionMetrics?.query_count || 0;
  const avgPerMsg = queryCount > 0 ? Math.round((sessionMetrics?.total_tokens || 0) / queryCount) : null;

  return (
    <div className="token-analytics">
      {/* Hero: context ring + I/O split */}
      <div className="tk-hero glass-panel">
        <div className="tk-hero__ring">
          <ContextGauge used={used} capacity={capacity} pct={pct} size={92} />
          <span className="tk-hero__ring-cap">{used.toLocaleString()} / {capacity.toLocaleString()}</span>
        </div>
        <div className="tk-hero__split">
          <div className="tk-split-head">
            <span><i className="dot dot-in" /> Input {prompt.toLocaleString()}</span>
            <span><i className="dot dot-out" /> Output {completion.toLocaleString()}</span>
          </div>
          <div className="tk-split-bar" role="img" aria-label={`Input ${prompt}, output ${completion} tokens`}>
            <span className="tk-split-in" style={{ width: `${inPct}%` }} />
            <span className="tk-split-out" style={{ width: `${outPct}%` }} />
          </div>
          <div className="tk-split-foot">
            <span>{Math.round(inPct)}% prompt</span>
            <span>{Math.round(outPct)}% completion</span>
          </div>
        </div>
      </div>

      {/* Stat tiles */}
      <div className="tk-tiles">
        <StatTile label="Input tokens" value={prompt.toLocaleString()} />
        <StatTile label="Output tokens" value={completion.toLocaleString()} />
        <StatTile label="Total tokens" value={total.toLocaleString()} accent="var(--accent)" />
        <StatTile
          label="Est. cost"
          value={`$${cost.toFixed(4)}`}
          sub="placeholder rate"
          accent="var(--hue-stream)"
        />
      </div>

      {/* Context window map */}
      <div className="tk-window glass-panel">
        <ContextWindowBar metrics={metrics} chunks={chunks} />
      </div>

      {/* Conversation stats */}
      <div className="tk-convo glass-panel">
        <div className="tk-convo__row">
          <span>Model</span>
          <strong className="metric-mono">{model}</strong>
        </div>
        <div className="tk-convo__row">
          <span>Model capacity</span>
          <strong>{capacity.toLocaleString()} tok</strong>
        </div>
        {queryCount > 0 && (
          <>
            <div className="tk-convo__row">
              <span>Conversation length</span>
              <strong>{queryCount} queries</strong>
            </div>
            <div className="tk-convo__row">
              <span>Avg tokens / message</span>
              <strong>{avgPerMsg?.toLocaleString()}</strong>
            </div>
            <div className="tk-convo__row">
              <span>Session total</span>
              <strong>{(sessionMetrics?.total_tokens || 0).toLocaleString()} tok</strong>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
