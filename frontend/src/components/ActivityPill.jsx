import { Circle, Loader2, Search, Cpu, Zap, Check, AlertTriangle } from "lucide-react";

/*
 * ActivityPill — the header's live "what is the AI doing" indicator.
 * Mirrors the pipeline's current phase without ever showing hidden reasoning.
 */

const TONES = {
  idle: { icon: Circle, spin: false },
  ready: { icon: Circle, spin: false },
  context: { icon: Search, spin: false },
  model: { icon: Loader2, spin: true },
  tool: { icon: Cpu, spin: true },
  stream: { icon: Zap, spin: false },
  done: { icon: Check, spin: false },
  error: { icon: AlertTriangle, spin: false }
};

export default function ActivityPill({ tone = "idle", label = "Ready" }) {
  const cfg = TONES[tone] || TONES.idle;
  const Icon = cfg.icon;
  return (
    <span className={`activity-pill tone-${tone}`} role="status" aria-live="polite">
      <Icon size={13} className={cfg.spin ? "spin" : ""} aria-hidden />
      <span className="activity-pill__label">{label}</span>
      {tone === "stream" && <span className="activity-pill__shimmer" aria-hidden />}
    </span>
  );
}
