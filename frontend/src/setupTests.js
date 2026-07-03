import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView; components that auto-scroll
// (e.g. ChatThread pinning to the latest message) call it in effects.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
