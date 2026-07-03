# AI Copilot Console Design System

This file is the source of truth for the current Indigo Console redesign.

## Identity

- Dark-first OLED console with a Linear-inspired indigo haze.
- Primary UI font: IBM Plex Sans.
- Data/code font: JetBrains Mono.
- Primary accent: indigo/violet, not teal. Teal is reserved for pipeline/tool semantics.

## Theme Tokens

All component styling should read from `frontend/src/styles.css` tokens instead of hardcoded colors.

- Canvas and surfaces: `--bg`, `--surface-1`, `--surface-2`, `--surface-3`, `--panel-glass`.
- Text: `--fg`, `--fg-muted`, `--fg-subtle`.
- Borders: `--border`, `--border-strong`, `--border-glass`.
- Accent: `--accent`, `--accent-hover`, `--accent-soft`, `--accent-glow`, `--on-accent`.
- Semantic: `--success`, `--warning`, `--danger`, `--info`.
- Pipeline hues: `--hue-prompt`, `--hue-context`, `--hue-memory`, `--hue-tools`, `--hue-model`, `--hue-stream`.
- Elevation: `--e1`, `--e2`, `--e3`, `--e-accent`.
- Radius: `--r-sm`, `--r-md`, `--r-lg`, `--r-pill`.
- Motion: `--dur-fast`, `--dur-base`, `--dur-slow`, `--ease-out`, `--ease-spring`.

The light theme lives under `:root[data-theme="light"]` and must preserve contrast of at least 4.5:1 for body text and controls.

## Layout Rules

- Keep the app as a work surface, not a marketing page.
- Sidebar, header, thread, and composer are persistent console chrome.
- Use glass panels for tools, repeated cards, modals, and detail containers. Avoid nested cards.
- The ambient glow is global (`body::before`) and should remain subtle.

## Interaction Rules

- Buttons and cards may lift or press slightly, but all motion must be covered by the existing `prefers-reduced-motion` guard.
- Focus rings must stay visible and token-driven.
- Use icon buttons where the action is familiar; add `title`/`aria-label` for icon-only controls.
- Popovers should use spring entrance motion, indigo-tinted borders, and theme-aware overlays.

## Component Rules

- Chat: user messages are accent tinted; assistant messages use avatar + neutral glass.
- Assistant details: Context, Trace, Agent Steps, and Metrics are collapsible per-message sections.
- PipelineRail: active node pulses with the stage hue; skipped nodes remain visible but subdued.
- Composer: a raised glass input pill owns mode selection, display preferences, token count, and send.
- Toasts and modals use the same indigo surface, scrim, border, and focus system.

## Cleanup Rules

Legacy tabbed response UI is retired. Do not reintroduce:

- `ResponsePanel.jsx`
- `ModeSelector.jsx`
- `QueryInput.jsx`
- CSS selectors for `response-tabs`, `tab-btn`, `tab-content`, `query-section`, `query-textarea`, or `mode-selector`.
