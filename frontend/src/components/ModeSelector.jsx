import { Cpu, Library, GitMerge, Sparkles } from "lucide-react";

const MODES = [
  { id: "auto", label: "auto", icon: Sparkles },
  { id: "llm", label: "llm", icon: Cpu },
  { id: "rag", label: "rag", icon: Library },
  { id: "agent", label: "agent", icon: GitMerge }
];

export default function ModeSelector({
  mode,
  setMode,
  showSources,
  setShowSources,
  showTrace,
  setShowTrace
}) {
  return (
    <div className="top-bar">
      <div className="mode-selector">
        {MODES.map((m) => {
          const Icon = m.icon;
          const isActive = mode === m.id;
          return (
            <button
              key={m.id}
              className={`mode-pill ${isActive ? "active" : ""}`}
              onClick={() => setMode(m.id)}
            >
              <Icon size={16} className={isActive ? "accent-teal" : ""} />
              {m.label}
              {isActive && <div className="active-underline" />}
            </button>
          );
        })}
      </div>

      <div className="toggles">
        <label className="toggle-switch">
          <input
            type="checkbox"
            checked={showSources}
            onChange={(e) => setShowSources(e.target.checked)}
          />
          <span className="slider"></span>
          <span className="label-text">Show sources</span>
        </label>
        <label className="toggle-switch">
          <input
            type="checkbox"
            checked={showTrace}
            onChange={(e) => setShowTrace(e.target.checked)}
          />
          <span className="slider"></span>
          <span className="label-text">Show agent trace</span>
        </label>
      </div>
    </div>
  );
}
