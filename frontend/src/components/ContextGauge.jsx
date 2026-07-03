/*
 * ContextGauge — circular ring showing context-window usage.
 * pct 0..1. Color ramps calm→amber→red. Center shows the percentage.
 */

function fmt(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

export default function ContextGauge({ used = 0, capacity = 0, pct = 0, size = 38 }) {
  const stroke = 4;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, pct));
  const offset = c * (1 - clamped);

  const color =
    clamped >= 0.9 ? "var(--danger)" : clamped >= 0.7 ? "var(--warning)" : "var(--hue-prompt)";
  const percentLabel = `${Math.round(clamped * 100)}%`;

  return (
    <span
      className="ctx-gauge"
      title={`Context: ${used.toLocaleString()} / ${capacity.toLocaleString()} tokens (${percentLabel})`}
      aria-label={`Context window ${percentLabel} used, ${used} of ${capacity} tokens`}
      role="img"
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--border)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 500ms var(--ease-out), stroke 300ms" }}
        />
      </svg>
      <span className="ctx-gauge__value">{percentLabel}</span>
    </span>
  );
}
