import { contextBreakdown } from "../lib/aiStatus.js";

/*
 * ContextWindowBar — horizontal segmented "memory map" of the context window.
 * Segments: System · History · Retrieved · Reserved(output) · Free.
 * Retrieved/System/History are estimates (see contextBreakdown).
 */

function pctOf(tokens, capacity) {
  return capacity > 0 ? (tokens / capacity) * 100 : 0;
}

export default function ContextWindowBar({ metrics = {}, chunks = [] }) {
  const { capacity, used, segments } = contextBreakdown(metrics, chunks);
  const usedPct = Math.round(pctOf(used, capacity));

  return (
    <div className="ctxwin">
      <div className="ctxwin__head">
        <span className="ctxwin__title">Context Window</span>
        <span className="ctxwin__usage">
          {used.toLocaleString()} / {capacity.toLocaleString()} · {usedPct}%
        </span>
      </div>

      <div className="ctxwin__bar" role="img" aria-label={`Context window ${usedPct}% used`}>
        {segments.map((s) => {
          const w = pctOf(s.tokens, capacity);
          if (w <= 0) return null;
          return (
            <span
              key={s.key}
              className={`ctxwin__seg seg-${s.key}`}
              style={{ width: `${w}%`, "--seg-hue": s.hue }}
              title={`${s.label}: ~${s.tokens.toLocaleString()} tokens (${Math.round(w)}%)`}
            />
          );
        })}
      </div>

      <ul className="ctxwin__legend">
        {segments.map((s) => (
          <li key={s.key} className="ctxwin__legend-item">
            <span className="ctxwin__swatch" style={{ background: s.hue }} aria-hidden />
            <span className="ctxwin__legend-label">{s.label}</span>
            <span className="ctxwin__legend-val">{s.tokens.toLocaleString()}</span>
          </li>
        ))}
      </ul>

      {usedPct >= 90 && (
        <div className="ctxwin__warn" role="status">
          Context nearly full — older turns may be trimmed.
        </div>
      )}
    </div>
  );
}
