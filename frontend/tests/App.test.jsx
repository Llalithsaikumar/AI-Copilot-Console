import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import App from "../src/App.jsx";

const api = vi.hoisted(() => ({
  generateSessionId: vi.fn(),
  getHistory: vi.fn(),
  getMetrics: vi.fn(),
  getSessionMetrics: vi.fn(),
  listDocuments: vi.fn(),
  listSessions: vi.fn(),
  queryCopilot: vi.fn(),
  queryCopilotStream: vi.fn(),
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  deleteSession: vi.fn()
}));

vi.mock("@clerk/react", () => ({
  useUser: () => ({
    isLoaded: true,
    isSignedIn: true,
    user: {
      id: "user_test",
      fullName: "Test User",
      primaryEmailAddress: { emailAddress: "t@example.com" },
      publicMetadata: {},
      organizationMemberships: []
    }
  }),
  useAuth: () => ({
    getToken: vi.fn(async () => "test-jwt")
  }),
  UserButton: () => null,
  Show: ({ children, when }) => {
    if (when === "signed-in") return <>{children}</>;
    return null;
  },
  SignIn: () => null
}));

vi.mock("../src/hooks/useApi.js", () => ({
  useApi: () => api
}));

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem("copilot:user_test:activeSession", "user_test:session-1");
  const queryResponse = {
    answer: "The report has one key risk.",
    session_id: "session-1",
    mode_used: "rag",
    citations: [
      {
        source: "report.txt",
        chunk_id: "chunk-1",
        chunk_index: 0,
        score: 0.9,
        quote: "A cited risk quote."
      }
    ],
    retrieved_chunks: [],
    agent_steps: [],
    trace: [
      { step: "route", meta: { mode: "rag" } },
      { step: "retrieve", meta: { chunks: 1 } }
    ],
    metrics: {
      latency_ms: 12,
      tokens: 5,
      retrieval_time_ms: 2,
      prompt_tokens: 2,
      completion_tokens: 3,
      total_tokens: 5,
      cost: 0.001,
      route_decision: "explicit_rag",
      cache_hit: false
    },
    request_id: "request-1"
  };
  api.generateSessionId.mockResolvedValue("user_test:session-1");
  api.listSessions.mockResolvedValue([]);
  api.getHistory.mockResolvedValue({ turns: [] });
  api.getMetrics.mockResolvedValue({
    avg_latency: 12,
    p95_latency: 12,
    cache_hit_rate: 0
  });
  api.getSessionMetrics.mockResolvedValue({
    session_id: "session-1",
    query_count: 1,
    total_tokens: 5,
    total_cost: 0.001,
    avg_latency_ms: 12
  });
  api.listDocuments.mockResolvedValue([]);
  api.queryCopilot.mockResolvedValue(queryResponse);
  api.queryCopilotStream.mockImplementation(async (payload, onToken, onFinal) => {
    onToken("The ");
    onToken("report has one key risk.");
    onFinal(queryResponse);
  });
  api.uploadDocument.mockResolvedValue({
    document_id: "doc-1",
    file_name: "profile.pdf",
    chunks_indexed: 3,
    chunks_skipped: 0,
    status: "indexed",
    suggested_queries: [
      "Find the email address in profile",
      "List the key skills from profile",
      "Summarize profile"
    ]
  });
});

afterEach(() => {
  cleanup();
});

async function renderReady() {
  render(<App />);
  await screen.findByTitle("user_test:session-1");
}

test("submits a query and renders the answer", async () => {
  await renderReady();
  const typedQuery = `query-${Date.now()}`;

  fireEvent.change(screen.getByLabelText("Query"), {
    target: { value: typedQuery }
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));

  await waitFor(() =>
    expect(screen.getByText("The report has one key risk.")).toBeInTheDocument()
  );
  expect(api.queryCopilotStream).toHaveBeenCalledWith(
    expect.objectContaining({
      query: typedQuery,
      mode: "auto"
    }),
    expect.any(Function),
    expect.any(Function),
    expect.any(Function)
  );
});

test("submits a query when Enter is pressed in the textarea", async () => {
  await renderReady();
  const typedQuery = `keyboard-${Date.now()}`;

  const textarea = screen.getByLabelText("Query");
  fireEvent.change(textarea, {
    target: { value: typedQuery }
  });
  fireEvent.keyDown(textarea, { key: "Enter", code: "Enter" });

  await waitFor(() =>
    expect(api.queryCopilotStream).toHaveBeenCalledWith(
      expect.objectContaining({
        query: typedQuery
      }),
      expect.any(Function),
      expect.any(Function),
      expect.any(Function)
    )
  );
});

test("shows suggested queries after upload and copies one into the composer", async () => {
  await renderReady();

  const file = new File(["profile text"], "profile.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText(/upload/i), {
    target: { files: [file] }
  });

  const suggestion = await screen.findByRole("button", {
    name: "Find the email address in profile"
  });
  fireEvent.click(suggestion);

  expect(api.uploadDocument).toHaveBeenCalledWith(file, expect.any(String));
  expect(screen.getByLabelText("Query")).toHaveValue(
    "Find the email address in profile"
  );
});

test("streams tokens before final response", async () => {
  await renderReady();

  fireEvent.change(screen.getByLabelText("Query"), {
    target: { value: "stream please" }
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));

  await waitFor(() =>
    expect(screen.getByText("The report has one key risk.")).toBeInTheDocument()
  );
  expect(api.queryCopilotStream).toHaveBeenCalled();
});

test("toggles source visibility", async () => {
  await renderReady();

  fireEvent.change(screen.getByLabelText("Query"), {
    target: { value: "show sources" }
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));

  await screen.findByText(/report\.txt/);
  fireEvent.click(screen.getByLabelText("Show sources"));

  expect(screen.queryByText(/report\.txt/)).not.toBeInTheDocument();
});

test("toggles trace visibility", async () => {
  await renderReady();

  fireEvent.change(screen.getByLabelText("Query"), {
    target: { value: "show trace" }
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));

  fireEvent.click(await screen.findByRole("button", { name: "Trace" }));
  await screen.findByText("route");
  fireEvent.click(screen.getByLabelText("Show agent trace"));

  expect(screen.getByText("Trace is hidden.")).toBeInTheDocument();
});

test("falls back to blocking query when streaming fails", async () => {
  api.queryCopilotStream.mockRejectedValueOnce(new Error("stream failed"));
  await renderReady();

  fireEvent.change(screen.getByLabelText("Query"), {
    target: { value: "fallback please" }
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));

  await waitFor(() =>
    expect(api.queryCopilot).toHaveBeenCalledWith(
      expect.objectContaining({ query: "fallback please" })
    )
  );
  expect(screen.getByText("The report has one key risk.")).toBeInTheDocument();
});
