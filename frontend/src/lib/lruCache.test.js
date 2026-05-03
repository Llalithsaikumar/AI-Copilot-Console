import { describe, it, expect } from "vitest";
import { createLruCache } from "./lruCache.js";

describe("createLruCache", () => {
  it("evicts oldest when over capacity", () => {
    const lru = createLruCache(2);
    lru.set("a", 1);
    lru.set("b", 2);
    lru.set("c", 3);
    expect(lru.get("a")).toBeUndefined();
    expect(lru.get("b")).toBe(2);
    expect(lru.get("c")).toBe(3);
  });

  it("refreshes order on get", () => {
    const lru = createLruCache(2);
    lru.set("a", 1);
    lru.set("b", 2);
    expect(lru.get("a")).toBe(1);
    lru.set("c", 3);
    expect(lru.get("a")).toBe(1);
    expect(lru.get("b")).toBeUndefined();
  });
});
