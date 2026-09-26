# ARIA patterns mapped to Safe Harbor components

Sources: [APG Dialog (Modal)](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [APG Disclosure](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/), [APG Button](https://www.w3.org/WAI/ARIA/apg/patterns/button/), [APG Slider](https://www.w3.org/WAI/ARIA/apg/patterns/slider/), [APG Toolbar](https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/), [APG Listbox](https://www.w3.org/WAI/ARIA/apg/patterns/listbox/), [MDN live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions), [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility).

Rule zero: native element first (`<button>`, `<input type="range">`, `<details>`), ARIA only to fill gaps. Wrong ARIA is worse than none.

## 1. Drawers (Harness, Inspector, Presentation dossier) — Modal dialog
Current: `role="dialog" aria-modal="true"` + `useDialogFocus` (`frontend/src/safe-harbor/dialogFocus.ts`) which focuses the first control, wraps Tab, restores focus on unmount.
Contract:
- Container: `role="dialog"`, `aria-modal="true"`, name via `aria-labelledby` pointing at the visible drawer title (prefer over `aria-label` when a heading exists). Optional `aria-describedby` for a short summary only.
- On open, focus goes inside. For long, structured content (evidence tables), APG advises focusing a static heading with `tabindex="-1"` rather than the first button, so the start of content stays in view.
- Tab / Shift+Tab cycle within the dialog; Escape closes.
- On close, focus returns to the invoking control; if it no longer exists, move it to a logical nearby element (e.g. the selected candidate card).
- Background must be inert: set the `inert` attribute on the app root sibling(s) while open (native, baseline) — this also blocks screen-reader virtual cursor, which a Tab-trap alone does not.
- Scrim click may close; it must not be the *only* close method. Close button needs a name ("Close evidence inspection").
- Gaps to check in `useDialogFocus`: selector misses `[tabindex]:not([tabindex="-1"])` > 0 and `[contenteditable]`, `iframe`; no `inert` on background; nested dialogs (dossier over drawer) need a stack so only the top one traps.

## 2. Toggle buttons (candidate list, Follow, mode pills)
- Use `<button aria-pressed="true|false">`. The label must stay constant while state changes (don't flip "Follow"→"Unfollow" *and* use `aria-pressed`).
- For a single-select candidate list, `aria-pressed` on each button is acceptable; alternatively a `role="listbox"` with `aria-selected` + arrow-key roving focus. Don't mix both. If items open a drawer on activation, keep them as buttons.

## 3. Disclosure (collapsible sections, "show more evidence")
- Trigger is a `<button aria-expanded>` with `aria-controls="<panel id>"`; panel hidden with `hidden` when collapsed. Enter/Space toggles. `<details><summary>` is a valid native alternative.

## 4. Timeline scrubber — Slider
- Best: `<input type="range" min max step value>` with `aria-valuetext` like "Commit 42 of 118, 14:03:21". Native gets keys for free.
- Custom slider: `role="slider"` on the focusable thumb, `tabindex="0"`, `aria-valuenow/min/max`, `aria-valuetext`, `aria-labelledby` (visible label) or `aria-label="Replay position"`.
- Keys: ←/↓ −1 step, →/↑ +1 step, Home = first, End = last (≈ Go Live), PageUp/PageDown larger jumps.
- APG's "Media Seek Slider" example is the closest analogue. Provide non-drag alternatives (WCAG 2.5.7): Prev/Next buttons already exist.

## 5. Playback controls — Toolbar (optional)
- Group Play/Pause, Next, Speed, Go Live, Follow in `role="toolbar" aria-label="Replay controls"`. With toolbar, use roving tabindex (one Tab stop, arrows move between). If that's too invasive, a plain `<div role="group" aria-label>` with each button tabbable is acceptable.
- Play/Pause: either one button with `aria-pressed` and fixed label "Play", or a label that swaps "Play"/"Pause" without `aria-pressed` — not both.

## 6. Live regions — streaming ledger status
- Create the region **once at mount** (empty), then update text; regions injected along with their content are often not announced.
- `role="status"` (implicit `aria-live="polite"`, `aria-atomic="true"`) for "Commit 43 recorded", "Run loaded", LIVE/RECORDED switch.
- `role="alert"` only for failures (run not found, stream disconnected).
- Throttle: announce a summary ("5 new commits") at most every few seconds during streaming; never make the whole ledger list live.
- `Presentation.tsx` already has `aria-live="polite"` on `.shp-mode` — keep that pattern.

## 7. Task graph (@xyflow/react)
- Defaults: nodes/edges Tab-focusable (`tabIndex=0`, `role="group"`), Enter/Space select, Escape clears, arrows move selected node (disable movement for a read-only graph via `nodesDraggable={false}` or `disableKeyboardA11y`).
- Set per-node `ariaRole` (e.g. `'listitem'`) and `domAttributes: { 'aria-label': 'Task X: passed', 'aria-roledescription': 'task' }`. Put interactive roles on inner controls, not the wrapper.
- `ariaLabelConfig` customizes the built-in instructions/live messages (e.g. remove "press delete to remove" text for a read-only graph).
- `autoPanOnNodeFocus` pans when a node gets focus — respect reduced motion (see motion doc).
- Provide an equivalent text list of tasks/status (a `<ul>` or table) near the graph; screen-reader users shouldn't need spatial navigation.

## 8. Genome browser (igv.js)
- Treat as a complex canvas: wrap in `<section aria-label="Genome view: <locus>">`, provide the locus and key features as adjacent text, and ensure the app's own zoom/locus buttons are real, named `<button>`s. Exclude igv's internal DOM from axe only if the violations are in third-party code (document the exclusion).

Content was rephrased for compliance with licensing restrictions.
