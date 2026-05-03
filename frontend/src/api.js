const API_BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "" : "https://ai-copilot-console.onrender.com");

let getTokenFn = async () => null;

/** Wire Clerk: `setApiAuth(() => getToken())` from a component. */
export function setApiAuth(getToken) {
  getTokenFn = getToken || (async () => null);
}

async function authHeaders(extra = {}) {
  const headers = { ...extra };
  try {
    const token = await getTokenFn();
    if (token) headers.Authorization = `Bearer ${token}`;
  } catch {
    /* leave unauthenticated */
  }
  return headers;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload.message || payload.detail || "Request failed";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return payload;
}

export async function queryCopilot(payload) {
  const response = await fetch(`${API_BASE}/v1/query`, {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function queryCopilotStream(payload, onToken, onFinal, onError) {
  const response = await fetch(`${API_BASE}/v1/query/stream`, {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload)
  });

  if (!response.ok || !response.body) {
    return queryCopilot(payload).then(onFinal);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "token") {
        onToken(event.text || "");
      } else if (event.type === "final") {
        onFinal(event.response);
      } else if (event.type === "error") {
        onError?.(event);
      }
    }
  }

  if (buffer.trim()) {
    const event = JSON.parse(buffer);
    if (event.type === "final") onFinal(event.response);
    if (event.type === "error") onError?.(event);
  }
}

export async function uploadDocument(file, sessionId) {
  const formData = new FormData();
  formData.append("file", file);
  if (sessionId) {
    formData.append("session_id", sessionId);
  }
  const response = await fetch(`${API_BASE}/v1/documents/upload`, {
    method: "POST",
    headers: await authHeaders({}),
    body: formData
  });
  return parseResponse(response);
}

export async function listDocuments(sessionId) {
  const suffix = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const response = await fetch(`${API_BASE}/v1/documents${suffix}`, {
    headers: await authHeaders()
  });
  return parseResponse(response);
}

export async function deleteDocument(documentId) {
  const response = await fetch(
    `${API_BASE}/v1/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE", headers: await authHeaders() }
  );
  return parseResponse(response);
}

export async function getHistory(sessionId) {
  const response = await fetch(
    `${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}/history`,
    { headers: await authHeaders() }
  );
  return parseResponse(response);
}

export async function listSessions() {
  const response = await fetch(`${API_BASE}/v1/sessions`, {
    headers: await authHeaders()
  });
  return parseResponse(response);
}

export async function deleteSession(sessionId) {
  const response = await fetch(
    `${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE", headers: await authHeaders() }
  );
  return parseResponse(response);
}

export async function getMetrics() {
  const response = await fetch(`${API_BASE}/metrics`, {
    headers: await authHeaders()
  });
  return parseResponse(response);
}

export async function getSessionMetrics(sessionId) {
  const response = await fetch(
    `${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}/metrics`,
    { headers: await authHeaders() }
  );
  return parseResponse(response);
}
