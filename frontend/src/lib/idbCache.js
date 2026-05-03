const DB_NAME = "copilot-console-cache";
const STORE = "entries";
const VERSION = 1;

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
  });
}

export async function idbGet(accountId, hashKey) {
  const db = await openDb();
  const key = `${accountId}:${hashKey}`;
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const store = tx.objectStore(STORE);
    const r = store.get(key);
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

export async function idbSet(accountId, hashKey, value) {
  const db = await openDb();
  const key = `${accountId}:${hashKey}`;
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const r = store.put(value, key);
    r.onsuccess = () => resolve();
    r.onerror = () => reject(r.error);
  });
}

export async function idbDeleteEntry(accountId, hashKey) {
  const db = await openDb();
  const key = `${accountId}:${hashKey}`;
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const r = store.delete(key);
    r.onsuccess = () => resolve();
    r.onerror = () => reject(r.error);
  });
}

export async function idbClearAccount(accountId) {
  const db = await openDb();
  const prefix = `${accountId}:`;
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const r = store.openCursor();
    r.onerror = () => reject(r.error);
    r.onsuccess = (ev) => {
      const cursor = ev.target.result;
      if (cursor) {
        if (String(cursor.key).startsWith(prefix)) {
          cursor.delete();
        }
        cursor.continue();
      } else {
        resolve();
      }
    };
  });
}

export async function idbInvalidateByDocumentId(accountId, documentId) {
  const db = await openDb();
  const prefix = `${accountId}:`;
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const r = store.openCursor();
    r.onerror = () => reject(r.error);
    r.onsuccess = (ev) => {
      const cursor = ev.target.result;
      if (cursor) {
        const val = cursor.value;
        if (
          String(cursor.key).startsWith(prefix) &&
          Array.isArray(val?.documentIds) &&
          val.documentIds.includes(documentId)
        ) {
          cursor.delete();
        }
        cursor.continue();
      } else {
        resolve();
      }
    };
  });
}
