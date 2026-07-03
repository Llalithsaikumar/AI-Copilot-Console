import { UserButton } from "@clerk/react";
import { Boxes, Wifi, WifiOff } from "lucide-react";
import ActivityPill from "./ActivityPill";
import ContextGauge from "./ContextGauge";
import ThemeToggle from "./ThemeToggle";
import {
  currentActivity,
  contextUsage,
  shortModel,
  readTokens
} from "../lib/aiStatus.js";

export default function AppHeader({
  title = "AI Copilot Console",
  subtitle,
  accountName,
  role,
  metrics = {},
  response,
  mode,
  isQuerying,
  hasCompletedTurn
}) {
  const activity = currentActivity({ response, mode, isQuerying, hasCompletedTurn });
  const { used, capacity, pct } = contextUsage(metrics);
  const { total } = readTokens(metrics);

  const provider = metrics.provider;
  const model = shortModel(metrics.model);
  const hasModel = !!(provider || model);

  // Connection: degraded only when the last turn surfaced an error.
  const connected = !response?.error;

  return (
    <header className="app-header command-header glass-panel">
      <div className="header-left">
        <h1 className="header-title">{title}</h1>
        {subtitle && <p className="header-sub">{subtitle}</p>}
      </div>

      <div className="header-status" role="group" aria-label="AI status">
        {hasModel && (
          <span className="model-chip" title={`Provider: ${provider || "—"} · Model: ${model || "—"}`}>
            <Boxes size={13} className="model-chip__icon" aria-hidden />
            <span className="model-chip__text">
              {provider ? `${provider} · ` : ""}
              {model || "model"}
            </span>
          </span>
        )}

        <span className={`conn-dot ${connected ? "is-online" : "is-degraded"}`} title={connected ? "Connected" : "Degraded — last request errored"}>
          {connected ? <Wifi size={13} aria-hidden /> : <WifiOff size={13} aria-hidden />}
          <span className="conn-dot__label">{connected ? "Connected" : "Degraded"}</span>
        </span>

        <ActivityPill tone={activity.tone} label={activity.label} />

        {total > 0 && <ContextGauge used={used} capacity={capacity} pct={pct} />}
      </div>

      <div className="header-right">
        <ThemeToggle />
        <div className="header-profile">
          <div className="header-profile-text">
            <span className="header-name">{accountName || "Account"}</span>
            {role && <span className="header-role">{role}</span>}
          </div>
          <UserButton afterSignOutUrl="/" />
        </div>
      </div>
    </header>
  );
}
