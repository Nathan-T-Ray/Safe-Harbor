# Vercel Web Interface Guidelines — distilled checklist

Source: https://github.com/vercel-labs/web-interface-guidelines (`command.md`, `AGENTS.md`, MIT); skill wrapper: https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines

Content was rephrased for compliance with licensing restrictions.

Use as a code-level audit. Output format (from the source command): group by file, one line per finding `path:line - problem`, `✓ pass` for clean files, no preamble.

## Accessibility & semantics
- Icon-only buttons (drawer close `×`, graph controls) need `aria-label`; decorative icons/SVG get `aria-hidden="true"`.
- Every input/select has a `<label htmlFor>` or `aria-label` (check `.open-run` input, timeline `<select>`, range slider).
- Actions = `<button>`, navigation = `<a>`. Flag `<div onClick>` / `<span onClick>` and SVG markers clickable without keyboard support (`.marker` in genome SVG).
- Async updates (run progress, errors, export results) announced via `aria-live="polite"`.
- Headings in order; add a skip link to main content.

## Focus
- Visible focus on every interactive element; prefer `:focus-visible`; never `outline:none` without replacement.
- Use `:focus-within` for compound controls; sticky bars/drawers must not hide the focused element.

## Forms
- Proper `type`/`inputmode`, meaningful `name`; never block paste; `spellCheck={false}` for IDs/run IDs.
- Submit stays enabled until the request starts, then shows progress; errors inline next to field, focus first error.
- Placeholders end in `…` and show an example value.

## Animation
- Honor `prefers-reduced-motion`; animate only `transform`/`opacity`; never `transition: all`.
- Correct `transform-origin`; animations interruptible.

## Typography & content
- `…` not `...`; loading text like `Loading…`.
- `font-variant-numeric: tabular-nums` on numeric columns, counters, coordinates.
- `text-wrap: balance` on headings.
- Long content: containers must truncate or wrap (`overflow-wrap:anywhere` for hashes/IDs); flex children need `min-width:0`.
- Render explicit empty states for empty arrays/strings.

## Performance
- Virtualize lists > ~50 items (evidence tables, event logs) or use `content-visibility:auto`.
- No layout reads in render; batch DOM reads/writes (relevant to igv.js/xyflow resize code).
- Preconnect/preload critical fonts with `font-display: swap`.

## Navigation & state
- URL reflects state: selected candidate, open drawer/tab, timeline position, run ID → query params so views are deep-linkable.
- Destructive actions need confirm or undo.

## Touch / layout
- `touch-action: manipulation`; `overscroll-behavior: contain` on drawers; during drag disable text selection.
- Drag/pan gestures (graph, genome) need click/keyboard alternatives.
- Prefer flex/grid over JS measurement; avoid accidental horizontal scrollbars.

## Dark theme (directly relevant)
- `color-scheme: dark` on `:root`/`<html>` (fixes native scrollbars, inputs) — currently missing in `styles.css`.
- `<meta name="theme-color">` matching background (`#0a1220`).
- Native `<select>`: explicit `background-color` and `color`.

## States & copy
- Hover/active/focus states more prominent than rest.
- Specific button labels, error messages include next step, numerals for counts.
- Dates/numbers via `Intl.DateTimeFormat` / `Intl.NumberFormat`; wrap identifiers (gene names, hashes) in `translate="no"`.

## Anti-patterns to grep for
`transition: all` · `outline: none` · `user-scalable=no` / `maximum-scale=1` · `onPaste` + `preventDefault` · clickable `div`/`span` · inputs without labels · icon buttons without `aria-label` · hardcoded date/number formatting · unjustified `autoFocus` · large `.map()` without virtualization.
