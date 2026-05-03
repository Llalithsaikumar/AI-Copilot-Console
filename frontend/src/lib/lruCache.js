/** Simple in-memory LRU keyed by string; values are arbitrary. */
export function createLruCache(maxSize) {
  const map = new Map();

  function get(key) {
    if (!map.has(key)) return undefined;
    const value = map.get(key);
    map.delete(key);
    map.set(key, value);
    return value;
  }

  function set(key, value) {
    if (map.has(key)) map.delete(key);
    map.set(key, value);
    while (map.size > maxSize) {
      const first = map.keys().next().value;
      map.delete(first);
    }
  }

  function clear() {
    map.clear();
  }

  return { get, set, clear };
}
