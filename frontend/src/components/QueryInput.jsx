import { Send, Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";

export default function QueryInput({
  query,
  setQuery,
  submitQuery,
  handleQueryKeyDown,
  isQuerying,
  suggestedQueries
}) {
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [query]);

  const charCount = query.length;
  const tokenEstimate = Math.ceil(charCount / 4);

  return (
    <div className="query-section">
      <div className="query-input-container glass-panel">
        <textarea
          ref={textareaRef}
          className="query-textarea"
          aria-label="Query"
          placeholder="Ask anything — grounded answers, retrieval, or agent reasoning..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleQueryKeyDown}
          rows={3}
        />
        
        <div className="query-footer">
          <div className="token-counter">
            {charCount} chars • ~{tokenEstimate} tokens
          </div>
          
          <button
            className="send-button teal-btn"
            disabled={isQuerying || !query.trim()}
            onClick={submitQuery}
          >
            {isQuerying ? (
              <>
                <Loader2 size={18} className="spin" />
                Processing
              </>
            ) : (
              <>
                <Send size={18} />
                Send <kbd>⌘↵</kbd>
              </>
            )}
          </button>
        </div>
      </div>

      {suggestedQueries && suggestedQueries.length > 0 && (
        <div className="suggested-queries">
          {suggestedQueries.map((sq) => (
            <button
              key={sq}
              className="suggestion-chip"
              onClick={() => {
                setQuery(sq);
                // Can't submit immediately safely without risking stale state, user can press send
              }}
            >
              {sq}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
