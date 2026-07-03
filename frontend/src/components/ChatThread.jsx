import { useEffect, useRef } from "react";
import { Bot, Sparkles, FileSearch, GitMerge, Lightbulb } from "lucide-react";
import MessageBubble from "./MessageBubble";

/*
 * ChatThread — the scrolling conversation. Shows a centered welcome + suggestion
 * cards when empty, otherwise the stacked message bubbles. Auto-sticks to the
 * bottom as tokens stream in.
 */

const STARTERS = [
  { icon: Sparkles, text: "Summarize the key risks in my latest document" },
  { icon: FileSearch, text: "What does the report say about revenue?" },
  { icon: GitMerge, text: "Compare the two approaches and recommend one" },
  { icon: Lightbulb, text: "Draft three follow-up questions for this topic" }
];

function Welcome({ suggestions, onPick }) {
  const cards = suggestions && suggestions.length > 0
    ? suggestions.map((text) => ({ icon: Lightbulb, text }))
    : STARTERS;

  return (
    <div className="welcome">
      <div className="welcome__mark">
        <Bot size={28} aria-hidden />
      </div>
      <h2 className="welcome__title">How can I help you today?</h2>
      <p className="welcome__subtitle">
        Ask for grounded answers, document retrieval, or multi-step agent reasoning.
      </p>
      <div className="welcome__grid">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <button
              key={c.text}
              type="button"
              className="welcome__card"
              onClick={() => onPick?.(c.text)}
            >
              <Icon size={18} className="welcome__card-icon" aria-hidden />
              <span>{c.text}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function ChatThread({
  messages,
  isQuerying,
  mode,
  hasCompletedTurn,
  showSources,
  showTrace,
  sessionMetrics,
  onRegenerate,
  canRegenerate,
  userInitials,
  welcomeSuggestions,
  onPickSuggestion
}) {
  const bottomRef = useRef(null);
  const lastContent = messages.length ? messages[messages.length - 1].content : "";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, lastContent]);

  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();

  return (
    <div className="chat-thread">
      <div className="chat-thread__inner">
        {messages.length === 0 ? (
          <Welcome suggestions={welcomeSuggestions} onPick={onPickSuggestion} />
        ) : (
          messages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLatest={index === lastAssistantIndex}
              isQuerying={isQuerying}
              mode={mode}
              hasCompletedTurn={hasCompletedTurn}
              showSources={showSources}
              showTrace={showTrace}
              sessionMetrics={sessionMetrics}
              onRegenerate={onRegenerate}
              canRegenerate={canRegenerate}
              userInitials={userInitials}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
