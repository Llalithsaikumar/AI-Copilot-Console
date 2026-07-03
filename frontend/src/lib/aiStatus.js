/*
 * aiStatus — frontend-only derivations for the status header and analytics.
 *
 * The backend does not send a model context capacity or a per-token price, so
 * these live here as frontend constants (clearly marked). Everything else is
 * derived from the real `metrics` payload the backend already returns.
 */

// Context window sizes (tokens). Matched by substring, longest first.
// [DETAILED_TOKEN_METRIC: model-capacity map] — adjust as providers change.
const CAPACITY = [
  ["gpt-4o-mini", 128000],
  ["gpt-4o", 128000],
  ["gpt-4-turbo", 128000],
  ["gpt-4", 8192],
  ["gpt-3.5", 16385],
  ["claude-3", 200000],
  ["claude", 200000],
  ["gemini-1.5", 1000000],
  ["gemini", 32000],
  ["llama-3", 128000],
  ["llama", 8192],
  ["mistral", 32000]
];
const DEFAULT_CAPACITY = 32000;

// Approx USD per 1K tokens [input, output].
// [DETAILED_TOKEN_METRIC: per-model pricing] — placeholder rates.
const PRICING = [
  ["gpt-4o-mini", [0.00015, 0.0006]],
  ["gpt-4o", [0.005, 0.015]],
  ["gpt-4-turbo", [0.01, 0.03]],
  ["gpt-4", [0.03, 0.06]],
  ["gpt-3.5", [0.0005, 0.0015]],
  ["claude-3", [0.003, 0.015]],
  ["gemini-1.5", [0.00125, 0.005]],
  ["gemini", [0.0005, 0.0015]],
  ["llama", [0.0002, 0.0002]]
];
const DEFAULT_PRICE = [0.001, 0.002];

function matchBy(table, model, fallback) {
  const key = String(model || "").toLowerCase();
  for (const [needle, value] of table) {
    if (key.includes(needle)) return value;
  }
  return fallback;
}

export function capacityFor(model) {
  return matchBy(CAPACITY, model, DEFAULT_CAPACITY);
}

export function costFor(model, promptTokens = 0, completionTokens = 0) {
  const [inRate, outRate] = matchBy(PRICING, model, DEFAULT_PRICE);
  return (Number(promptTokens) / 1000) * inRate + (Number(completionTokens) / 1000) * outRate;
}

export function shortModel(model) {
  if (!model) return "";
  return String(model).split("/").pop();
}

/** Normalize the varied metric key casings the app already tolerates. */
export function readTokens(metrics = {}) {
  const prompt = metrics.prompt_tokens ?? metrics.promptTokens ?? 0;
  const completion = metrics.completion_tokens ?? metrics.completionTokens ?? 0;
  const total =
    metrics.total_tokens ??
    metrics.totalTokens ??
    (Number(prompt) + Number(completion) || metrics.tokens || 0);
  return { prompt: Number(prompt), completion: Number(completion), total: Number(total) };
}

export function contextUsage(metrics = {}) {
  const { total } = readTokens(metrics);
  const capacity = capacityFor(metrics.model);
  const pct = capacity > 0 ? Math.min(1, total / capacity) : 0;
  return { used: total, capacity, pct };
}

/** Rough token estimate for a text blob (~4 chars/token). */
export function estimateTokens(text) {
  return Math.ceil((text?.length || 0) / 4);
}

/*
 * contextBreakdown — segments the context window into a memory map.
 * The backend reports prompt/completion totals but not the internal split,
 * so retrieved/system/history are ESTIMATES derived from the retrieved chunk
 * text and a fixed system-scaffold guess. Labeled as such in the UI.
 */
export function contextBreakdown(metrics = {}, chunks = []) {
  const { prompt, completion } = readTokens(metrics);
  const capacity = capacityFor(metrics.model);

  const SYSTEM_SCAFFOLD = 400; // [DETAILED_TOKEN_METRIC: system prompt size]
  const retrievedRaw = (chunks || []).reduce((a, c) => a + estimateTokens(c.text), 0);

  const system = Math.min(SYSTEM_SCAFFOLD, prompt);
  const retrieved = Math.min(retrievedRaw, Math.max(0, prompt - system));
  const conversation = Math.max(0, prompt - system - retrieved);
  const reserved = completion || 0;
  const used = system + retrieved + conversation + reserved;
  const free = Math.max(0, capacity - used);

  return {
    capacity,
    used,
    segments: [
      { key: "system", label: "System", tokens: system, hue: "var(--hue-prompt)" },
      { key: "conversation", label: "History", tokens: conversation, hue: "var(--hue-memory)" },
      { key: "retrieved", label: "Retrieved", tokens: retrieved, hue: "var(--hue-context)" },
      { key: "reserved", label: "Reserved", tokens: reserved, hue: "var(--hue-model)" },
      { key: "free", label: "Free", tokens: free, hue: "var(--border-strong)" }
    ]
  };
}

/**
 * The single "what is the AI doing right now" signal for the ActivityPill.
 * tone drives color; label is the human string. Never exposes reasoning.
 */
export function currentActivity({ response, mode, isQuerying, hasCompletedTurn }) {
  if (response?.error) return { tone: "error", label: "Error" };
  if (isQuerying) {
    const streaming = (response?.answer || "").length > 0;
    if (streaming) return { tone: "stream", label: "Streaming…" };
    if (mode === "rag" || mode === "agent") return { tone: "context", label: "Retrieving context…" };
    return { tone: "model", label: "Thinking…" };
  }
  if (hasCompletedTurn) return { tone: "done", label: "Idle" };
  return { tone: "idle", label: "Ready" };
}
