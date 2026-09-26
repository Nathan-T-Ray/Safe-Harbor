# Interface Guidelines Checklist (Safe-Harbor adaptation)

Sources: [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) (MIT) · [NN/g 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) · [WAI-ARIA APG](https://www.w3.org/WAI/ARIA/apg/patterns/)

Content was rephrased for compliance with licensing restrictions.

Use the IDs when citing a fix. Each item has a **Check** (how to find violations) and a **Fix** (what to do in plain CSS/React).

## Interaction (IG-I)
- **IG-I1 Keyboard parity.** Every click target (graph nodes, timeline scrubber, drawer buttons, header actions) can be reached with Tab and activated with Enter/Space. *Check:* look for `onClick` on `div`/`span` in `*.tsx`. *Fix:* use `<button type="button">`. For @xyflow nodes, make sure `nodesFocusable` is on and focused nodes get a visible style.
- **IG-I2 Visible focus.** Style `:focus-visible` (not `:focus`) with a ring that meets at least Lc 45, e.g. `outline: 2px solid var(--cyan); outline-offset: 2px`. Sticky bars must not cover the focused element; use `scroll-margin` / `scroll-padding-top` for that.
- **IG-I3 Hit targets.** Aim for at least 24×24 px on desktop. Tiny icon buttons (drawer close, legend toggles) can grow their hit area with padding or a `::before` inset, without changing how they look.
- **IG-I4 Loading buttons.** Keep the label and add an indicator. Use the `…` character for in-progress copy ("Running…", "Loading genome…").
- **IG-I5 Flicker guard.** Wait about 150–300 ms before showing a spinner/skeleton, then keep it visible for at least about 300–500 ms.
- **IG-I6 Destructive and irreversible actions** (re-run, discard, publish) need a confirm step or an Undo.
- **IG-I7 URL as state.** Put the selected run, open drawer, active tab, and genome locus in query params so refresh, Back, and share all work. `URLSearchParams` + `history.replaceState` is enough; no new dependency.
- **IG-I8 Announce async changes.** Use a polite `aria-live` region for run status, validation, and toasts. Today it exists only in `Presentation.tsx`.
- **IG-I9 Gestures need alternatives.** Graph pan/zoom and igv.js drag need button or keyboard equivalents (zoom +/−, fit view, locus input).
- **IG-I10 Links vs buttons.** Navigation uses `<a href>`; actions use `<button>`.

## Animation (IG-A)
- **IG-A1** Every animation gets a `@media (prefers-reduced-motion: reduce)` override.
- **IG-A2** Animate only `transform` and `opacity`, and list the properties explicitly (no `transition: all`).
- **IG-A3** Animation should explain cause and effect (a drawer sliding in from its edge), not decorate. User input must be able to interrupt it.

## Layout (IG-L)
- **IG-L1** Use flex/grid and intrinsic sizing, not JS measurement. Where the graph and igv canvas need a size, give their container an explicit height or `min-height`.
- **IG-L2** Check at 1280, 1440, 1920, and a narrow width about 390 px. There should be no stray double scrollbars.
- **IG-L3** Nested radii: an inner element's radius should be at most the outer radius minus the padding.

## Content (IG-C)
- **IG-C1 Every state is designed:** empty, sparse, dense, error, and loading. See `04-state-patterns.md`.
- **IG-C2 Don't rely on color alone.** Pass/fail/blocked status needs a text label or icon as well as cyan/amber.
- **IG-C3 Tabular numbers.** Metrics, coordinates, and timestamps get `font-variant-numeric: tabular-nums`.
- **IG-C4** Name icon-only buttons with `aria-label`, and hide decorative SVGs with `aria-hidden="true"`.
- **IG-C5** Use native semantics before ARIA: real `<table>` for tabular evidence, and a proper `<h1>`–`<h3>` hierarchy.
- **IG-C6** Layouts must survive very long IDs and hashes: `overflow-wrap: anywhere` or truncation with ellipsis plus a `title`/tooltip.
- **IG-C7** `<title>` should reflect the current run or view.
- **IG-C8 No dead ends.** Every error or empty view offers a next action.

## Forms (IG-F)
- **IG-F1** Every input has an associated `<label>`, and clicking the label focuses the input.
- **IG-F2** Don't pre-disable submit. Validate on submit, show the error next to the field, and focus the first invalid field.
- **IG-F3** Disable submit only while the request is in flight, and guard against double submission.
- **IG-F4** Allow free typing in numeric fields and validate afterwards, rather than blocking keys. Use `inputmode="decimal"` for numbers.
- **IG-F5** Turn off `spellcheck` for IDs, loci, and hashes. Placeholders show an example (e.g. `chr1:1,000,000-1,050,000`).
- **IG-F6** On Windows, a native `<select>` in a dark theme needs explicit `background-color` and `color`.

## Heuristic mapping (NN/g)
Tag findings with: H1 visibility of system status · H2 match with the real world (domain terms) · H3 user control and freedom (Esc, Undo, Cancel) · H4 consistency and standards · H5 error prevention · H6 recognition over recall (show the current run/locus) · H7 flexibility and efficiency (shortcuts) · H8 minimalist design · H9 helping users recover from errors · H10 help and documentation.
