import { useEffect, useRef, useState } from "react";
import {
  Send,
  Loader2,
  Sparkles,
  Cpu,
  Library,
  GitMerge,
  ChevronDown,
  SlidersHorizontal,
  Check
} from "lucide-react";

/*
 * Composer — the bottom input pill. Folds in the former ModeSelector (now a
 * compact dropdown) and the display-preference toggles (now a popover), so the
 * chat stays clean and the console power is one tap away.
 */

const MODES = [
  { id: "auto", label: "Auto", icon: Sparkles, hue: "var(--accent)", tip: "Routes to LLM, RAG, or Agent automatically." },
  { id: "llm", label: "LLM", icon: Cpu, hue: "var(--hue-prompt)", tip: "Direct model answer — no retrieval." },
  { id: "rag", label: "RAG", icon: Library, hue: "var(--hue-context)", tip: "Retrieve context first, answer with citations." },
  { id: "agent", label: "Agent", icon: GitMerge, hue: "var(--hue-tools)", tip: "Planner–executor with tools." }
];

export default function Composer({
  query,
  setQuery,
  submitQuery,
  handleQueryKeyDown,
  isQuerying,
  suggestedQueries,
  mode,
  setMode,
  showSources,
  setShowSources,
  showTrace,
  setShowTrace
}) {
  const textareaRef = useRef(null);
  const modeRef = useRef(null);
  const prefsRef = useRef(null);
  const [modeOpen, setModeOpen] = useState(false);
  const [prefsOpen, setPrefsOpen] = useState(false);

  // Auto-grow the textarea up to a cap.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [query]);

  // Dismiss popovers on outside click / Escape.
  useEffect(() => {
    function onDown(e) {
      if (modeRef.current && !modeRef.current.contains(e.target)) setModeOpen(false);
      if (prefsRef.current && !prefsRef.current.contains(e.target)) setPrefsOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") {
        setModeOpen(false);
        setPrefsOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const active = MODES.find((m) => m.id === mode) || MODES[0];
  const ActiveIcon = active.icon;
  const charCount = query.length;
  const tokenEstimate = Math.ceil(charCount / 4);

  return (
    <div className="composer">
      {suggestedQueries && suggestedQueries.length > 0 && (
        <div className="suggested-queries">
          {suggestedQueries.map((sq) => (
            <button
              key={sq}
              type="button"
              className="suggestion-chip"
              onClick={() => setQuery(sq)}
            >
              {sq}
            </button>
          ))}
        </div>
      )}

      <div className="composer-box">
        <textarea
          ref={textareaRef}
          className="composer-textarea"
          aria-label="Query"
          placeholder="Ask anything — grounded answers, retrieval, or agent reasoning…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleQueryKeyDown}
          rows={1}
        />

        <div className="composer-footer">
          <div className="composer-tools">
            {/* Mode dropdown */}
            <div className="composer-menu" ref={modeRef}>
              <button
                type="button"
                className="composer-chip"
                aria-haspopup="listbox"
                aria-expanded={modeOpen}
                style={{ "--mode-hue": active.hue }}
                onClick={() => {
                  setModeOpen((v) => !v);
                  setPrefsOpen(false);
                }}
              >
                <ActiveIcon size={15} style={{ color: active.hue }} aria-hidden />
                <span>{active.label}</span>
                <ChevronDown size={14} aria-hidden />
              </button>
              {modeOpen && (
                <div className="composer-popover mode-menu" role="listbox" aria-label="Response mode">
                  {MODES.map((m) => {
                    const Icon = m.icon;
                    const isActive = mode === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        role="option"
                        aria-selected={isActive}
                        className={`mode-option ${isActive ? "active" : ""}`}
                        onClick={() => {
                          setMode(m.id);
                          setModeOpen(false);
                        }}
                      >
                        <Icon size={16} style={{ color: m.hue }} aria-hidden />
                        <span className="mode-option__body">
                          <strong>{m.label}</strong>
                          <small>{m.tip}</small>
                        </span>
                        {isActive && <Check size={14} className="accent" aria-hidden />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Display preferences popover */}
            <div className="composer-menu" ref={prefsRef}>
              <button
                type="button"
                className="composer-chip icon-only"
                aria-haspopup="menu"
                aria-expanded={prefsOpen}
                aria-label="Display preferences"
                title="Display preferences"
                onClick={() => {
                  setPrefsOpen((v) => !v);
                  setModeOpen(false);
                }}
              >
                <SlidersHorizontal size={15} aria-hidden />
              </button>
              {prefsOpen && (
                <div className="composer-popover prefs-menu" role="menu">
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={showSources}
                      onChange={(e) => setShowSources(e.target.checked)}
                    />
                    <span className="slider" />
                    <span className="label-text">Show sources</span>
                  </label>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={showTrace}
                      onChange={(e) => setShowTrace(e.target.checked)}
                    />
                    <span className="slider" />
                    <span className="label-text">Show agent trace</span>
                  </label>
                </div>
              )}
            </div>

            <span className="composer-count">
              {charCount} chars · ~{tokenEstimate} tok
            </span>
          </div>

          <button
            type="button"
            className="composer-send"
            disabled={isQuerying || !query.trim()}
            onClick={() => submitQuery()}
          >
            {isQuerying ? (
              <>
                <Loader2 size={16} className="spin" aria-hidden /> Sending
              </>
            ) : (
              <>
                <Send size={16} aria-hidden /> Send
              </>
            )}
          </button>
        </div>
      </div>

      <p className="composer-hint">
        Press <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
      </p>
    </div>
  );
}
