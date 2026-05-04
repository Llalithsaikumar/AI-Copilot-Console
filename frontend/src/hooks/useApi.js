import { useCallback } from 'react';
import { useAuth } from '@clerk/react';
import { fetchWithAuth, API_BASE, parseJwt } from '../lib/apiClient';

export function useApi() {
  const { getToken } = useAuth();

  const generateSessionId = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("Not authenticated");
    
    const payload = parseJwt(token);
    if (!payload?.sub) throw new Error("Invalid token payload");
    
    return `${payload.sub}:${crypto.randomUUID()}`;
  }, [getToken]);

  const queryCopilot = useCallback(async (payload) => {
    const res = await fetchWithAuth(`${API_BASE}/v1/query`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }, getToken);
    return res.json();
  }, [getToken]);

  const queryCopilotStream = useCallback(async (payload, onToken, onFinal, onError) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/v1/query/stream`, {
        method: 'POST',
        body: JSON.stringify(payload)
      }, getToken);

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
          try {
            const event = JSON.parse(line);
            if (event.type === "token") onToken(event.text || "");
            else if (event.type === "final") onFinal(event.response);
            else if (event.type === "error") onError?.(event);
          } catch (e) {
            console.error("Failed to parse stream chunk", e);
          }
        }
      }

      if (buffer.trim()) {
        const event = JSON.parse(buffer);
        if (event.type === "final") onFinal(event.response);
        if (event.type === "error") onError?.(event);
      }
    } catch (err) {
      onError?.(err);
    }
  }, [getToken]);

  const uploadDocument = useCallback(async (file, sessionId) => {
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) formData.append("session_id", sessionId);

    const res = await fetchWithAuth(`${API_BASE}/v1/documents/upload`, {
      method: 'POST',
      body: formData
    }, getToken);
    
    return res.json();
  }, [getToken]);

  const listDocuments = useCallback(async (sessionId) => {
    const suffix = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
    const res = await fetchWithAuth(`${API_BASE}/v1/documents${suffix}`, {}, getToken);
    return res.json();
  }, [getToken]);

  const deleteDocument = useCallback(async (documentId) => {
    const res = await fetchWithAuth(`${API_BASE}/v1/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE'
    }, getToken);
    return res.json();
  }, [getToken]);

  const listSessions = useCallback(async () => {
    const res = await fetchWithAuth(`${API_BASE}/v1/sessions`, {}, getToken);
    return res.json();
  }, [getToken]);

  const getHistory = useCallback(async (sessionId) => {
    const res = await fetchWithAuth(`${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}/history`, {}, getToken);
    return res.json();
  }, [getToken]);

  const deleteSession = useCallback(async (sessionId) => {
    const res = await fetchWithAuth(`${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE'
    }, getToken);
    return res.json();
  }, [getToken]);

  const getMetrics = useCallback(async () => {
    const res = await fetchWithAuth(`${API_BASE}/metrics`, {}, getToken);
    return res.json();
  }, [getToken]);

  const getSessionMetrics = useCallback(async (sessionId) => {
    const res = await fetchWithAuth(`${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}/metrics`, {}, getToken);
    return res.json();
  }, [getToken]);

  return {
    generateSessionId,
    queryCopilot,
    queryCopilotStream,
    uploadDocument,
    listDocuments,
    deleteDocument,
    listSessions,
    getHistory,
    deleteSession,
    getMetrics,
    getSessionMetrics,
  };
}
