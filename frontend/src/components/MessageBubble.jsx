import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bot,
  FileText,
  Zap,
  Copy,
  Check,
  RefreshCw,
  Coins,
  Timer,
  AlertCircle
} from "lucide-react";
import AssistantDetails from "./AssistantDetails";
import PipelineRail from "./PipelineRail";
import { readTokens, costFor } from "../lib/aiStatus.js";

const markdownComponents = {
  table({ children, ...props }) {
    return (
      <div className="markdown-table-wrap">
        <table {...props}>{children}</table>
      </div>
    );
  }
};

/* Estimate live generation speed (~4 chars/token) from answer growth. */
function useStreamStats(answer, streaming) {
  const [rate, setRate] = useState(0);
  const startRef = useRef(null);
  const startLenRef = useRef(0);

  useEffect(() => {
    if (!streaming) {
      startRef.current = null;
      startLenRef.current = 0;
      return;
    }
    const len = answer?.length || 0;
    const now = Date.now();
    if (startRef.current == null && len > 0) {
      startRef.current = now;
      startLenRef.current = len;
      return;
    }
    if (startRef.current != null) {
      const elapsed = (now - startRef.current) / 1000;
      const chars = len - startLenRef.current;
      if (elapsed > 0.25 && chars > 0) {
        setRate(Math.max(1, Math.round(chars / 4 / elapsed)));
      }
    }
  }, [answer, streaming]);

  return rate;
}

function UserMessage({ message, userInitials }) {
  return (
    <div className="msg msg-user">
      <div className="msg-body">
        <div className="msg-bubble">{message.content}</div>
      </div>
      <div className="msg-avatar msg-avatar--user" aria-hidden>
        {userInitials || "You"}
      </div>
    </div>
  );
}

function AssistantMessage({
  message,
  isLatest,
  isQuerying,
  mode,
  hasCompletedTurn,
  showSources,
  showTrace,
  sessionMetrics,
  onRegenerate,
  canRegenerate
}) {
  const [copied, setCopied] = useState(false);
  const streaming = !!message.streaming;
  const tokPerSec = useStreamStats(message.content, streaming);

  const citations = message.citations || [];
  const m = message.metrics || {};
  const { prompt: inTok, completion: outTok, total: totalTok } = readTokens(m);
  const genMs = Math.round(m.latency_ms ?? m.latencyMs ?? 0);
  const cost = costFor(m.model, inTok, outTok);
  const retrievalCount =
    m.retrieval_chunk_count ?? m.retrievalChunkCount ?? message.chunks?.length ?? 0;
  const route = m.route_decision || m.routeDecision || message.mode || "route";
  const modelLabel = m.model ? String(m.model).split("/").pop() : "";

  const complete = !streaming && !!message.content && !message.error;

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(message.content || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  // Adapter so PipelineRail keeps its backend-shaped field names.
  const railResponse = {
    answer: message.content,
    trace: message.trace,
    metrics: message.metrics,
    retrieved_chunks: message.chunks,
    agent_steps: message.agentSteps,
    error: message.error
  };

  return (
    <div className="msg msg-assistant">
      <div className="msg-avatar msg-avatar--bot" aria-hidden>
        <Bot size={18} />
      </div>
      <div className="msg-body">
        <div className="msg-bubble">
          {streaming && !message.content ? (
            <div className="typing" aria-label="Assistant is thinking">
              <span />
              <span />
              <span />
            </div>
          ) : message.error ? (
            <div className="msg-error">
              <AlertCircle size={16} aria-hidden />
              <span>{message.content || "Something went wrong."}</span>
            </div>
          ) : (
            <div className={`markdown-body ${streaming ? "is-streaming" : "answer-complete"}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content || ""}
              </ReactMarkdown>
              {streaming && <span className="stream-cursor" aria-hidden />}
            </div>
          )}

          {streaming && message.content && (
            <div className="stream-stats" role="status" aria-live="off">
              <Zap size={12} className="accent" aria-hidden />
              <span>Generating{tokPerSec > 0 ? ` · ≈ ${tokPerSec} tok/s` : "…"}</span>
            </div>
          )}
        </div>

        {complete && (
          <div className="turn-metrics" aria-label="Response metrics">
            {genMs > 0 && (
              <span className="turn-metric">
                <Timer size={12} aria-hidden />
                <strong>{genMs}</strong>
                <small>ms</small>
              </span>
            )}
            {totalTok > 0 && (
              <span className="turn-metric" title={`Input ${inTok} · Output ${outTok}`}>
                <Coins size={12} aria-hidden />
                <strong>{totalTok.toLocaleString()}</strong>
                <small>tok</small>
              </span>
            )}
            {retrievalCount > 0 && (
              <span className="turn-metric">
                <FileText size={12} aria-hidden />
                <strong>{retrievalCount}</strong>
                <small>chunks</small>
              </span>
            )}
            <span className="turn-metric turn-metric--route">
              <Zap size={12} aria-hidden />
              <strong>{route}</strong>
              {modelLabel && <small>{modelLabel}</small>}
            </span>
          </div>
        )}

        {isLatest && isQuerying && (
          <PipelineRail
            response={railResponse}
            mode={mode}
            isQuerying={isQuerying}
            hasCompletedTurn={hasCompletedTurn}
          />
        )}

        {showSources && citations.length > 0 && (
          <div className="citations-section">
            <h3>Sources</h3>
            <div className="citations-list">
              {citations.map((c, i) => (
                <span key={i} className="citation-chip">
                  <FileText size={12} aria-hidden />
                  [{c.chunk_index}] {c.source}
                </span>
              ))}
            </div>
          </div>
        )}

        {complete && (
          <div className="message-actions">
            <div className="message-actions__btns">
              <button type="button" className="msg-action" onClick={copyAnswer} title="Copy answer">
                {copied ? (
                  <>
                    <Check size={13} className="accent" /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={13} /> Copy
                  </>
                )}
              </button>
              {isLatest && (
                <button
                  type="button"
                  className="msg-action"
                  onClick={onRegenerate}
                  disabled={!canRegenerate}
                  title="Regenerate a fresh response (skips cache)"
                >
                  <RefreshCw size={13} /> Regenerate
                </button>
              )}
            </div>
            <div className="message-actions__meta">
              {totalTok > 0 && (
                <span className="msg-meta" title={`Input ${inTok} · Output ${outTok}`}>
                  <Coins size={12} /> {totalTok.toLocaleString()} tok
                </span>
              )}
              {genMs > 0 && (
                <span className="msg-meta">
                  <Timer size={12} /> {genMs} ms
                </span>
              )}
              {cost > 0 && (
                <span className="msg-meta" title="Estimated cost (placeholder rate)">
                  <span className="msg-meta__dollar">$</span>
                  {cost.toFixed(4)}
                </span>
              )}
            </div>
          </div>
        )}

        {!streaming && (
          <AssistantDetails
            message={message}
            showTrace={showTrace}
            sessionMetrics={sessionMetrics}
          />
        )}
      </div>
    </div>
  );
}

export default function MessageBubble(props) {
  if (props.message.role === "user") {
    return <UserMessage message={props.message} userInitials={props.userInitials} />;
  }
  return <AssistantMessage {...props} />;
}
