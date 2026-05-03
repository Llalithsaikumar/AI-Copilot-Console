const LS_SESSIONS = (accountId) => `copilot:${accountId}:sessions`;
const LS_ACTIVE = (accountId) => `copilot:${accountId}:activeSession`;

export function readSessionRegistry(accountId) {
  try {
    const raw = localStorage.getItem(LS_SESSIONS(accountId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function writeSessionRegistry(accountId, sessions) {
  localStorage.setItem(LS_SESSIONS(accountId), JSON.stringify(sessions));
}

export function getActiveSessionId(accountId) {
  return localStorage.getItem(LS_ACTIVE(accountId)) || "";
}

export function setActiveSessionId(accountId, sessionId) {
  localStorage.setItem(LS_ACTIVE(accountId), sessionId);
}

export function upsertSessionRecord(accountId, record) {
  const list = readSessionRegistry(accountId);
  const idx = list.findIndex((s) => s.sessionId === record.sessionId);
  if (idx >= 0) list[idx] = { ...list[idx], ...record };
  else list.push(record);
  writeSessionRegistry(accountId, list);
}
