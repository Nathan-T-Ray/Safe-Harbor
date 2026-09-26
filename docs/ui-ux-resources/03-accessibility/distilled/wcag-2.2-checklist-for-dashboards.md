# WCAG 2.2 AA checklist for the Safe Harbor dashboard

Sources: [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/), [A11Y Project checklist](https://www.a11yproject.com/checklist/), [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/), [APCA](https://git.apcacontrast.com/).

Target: **WCAG 2.2 Level AA**. Each item: SC → what to check here → how to verify in E2E.

## Perceivable
- **1.1.1 Non-text content (A)** — icon-only buttons (play, next, close ×, zoom) need an accessible name (`aria-label` or visually-hidden text). Decorative SVGs get `aria-hidden="true"`. igv.js/graph canvases need a text summary nearby. *E2E:* `getByRole('button', { name: /close/i })` resolves.
- **1.3.1 Info & relationships (A)** — panels use headings (`h2/h3`) and `<section aria-label>`; key/value evidence uses `<dl>` or tables with `<th>`. Status pills must carry text, not just color.
- **1.4.1 Use of color (A)** — pass/fail/live/recorded pills must also differ by text or icon.
- **1.4.3 Contrast (AA)** — body text ≥ 4.5:1; large text (≥24px, or ≥18.66px bold) ≥ 3:1. Dark themes often fail on muted grey labels (`--muted`) and on text over tinted pills. *E2E:* axe rule `color-contrast`.
- **1.4.11 Non-text contrast (AA)** — button borders, focus rings, slider track/thumb, graph edges/handles ≥ 3:1 against adjacent colors.
- **1.4.4 / 1.4.10 / 1.4.12 Resize, reflow, text spacing (AA)** — at 200% zoom / 320 CSS px width, no content loss; drawers must scroll internally. *E2E:* viewport `{width:320}` and check no horizontal scroll on `document.documentElement`.
- **1.4.13 Content on hover/focus (AA)** — tooltips dismissible with Escape, hoverable, persistent.

## Operable
- **2.1.1 Keyboard (A)** — every click handler on a non-`<button>` element is a bug; timeline scrubber, speed control, candidate cards, graph nodes must be keyboard-operable.
- **2.1.2 No keyboard trap (A)** — drawers trap focus *only while open*; Escape must release.
- **2.1.4 Character key shortcuts (A)** — single-letter shortcuts (e.g. space for play outside a button) must be remappable/disable-able or only active on focus.
- **2.2.2 Pause, stop, hide (A)** — auto-advancing playback and camera-follow that lasts >5s need a visible pause/stop control (Follow toggle + Pause qualify if always reachable).
- **2.3.3 Animation from interactions (AAA, but adopt)** — honor `prefers-reduced-motion`; see `reduced-motion-and-auto-scroll.md`.
- **2.4.3 Focus order (A)** — opening a drawer moves focus into it; closing returns to the invoker.
- **2.4.7 Focus visible (AA)** — never `outline:none` without a replacement; use `:focus-visible { outline: 2px solid <≥3:1 color>; outline-offset: 2px }`.
- **2.4.11 Focus not obscured (AA, new)** — the focused element must not be fully hidden by the sticky footer, timeline bar, or a scrim. Use `scroll-padding-bottom` equal to sticky bar height.
- **2.5.3 Label in name (A)** — the accessible name must contain the visible label text.
- **2.5.7 Dragging movements (AA, new)** — scrubber drag and graph pan need a non-drag alternative (arrow keys, step buttons, Fit View control).
- **2.5.8 Target size minimum (AA, new)** — pointer targets ≥ 24×24 CSS px or sufficiently spaced; small pills/chips and × buttons are typical failures. *E2E:* axe rule `target-size` (tag `wcag22aa`).

## Understandable
- **3.2.1 / 3.2.2 On focus / on input (A)** — focusing or selecting a candidate must not open a drawer or navigate by itself unless the user activates it.
- **3.3.1 / 3.3.2 Errors & labels (A)** — run-ID input has a `<label>`; errors are text linked with `aria-describedby`.

## Robust
- **4.1.2 Name, role, value (A)** — toggles expose `aria-pressed`, disclosures `aria-expanded`, sliders `aria-valuenow/min/max/valuetext`, dialogs `role="dialog"` + `aria-modal` + name.
- **4.1.3 Status messages (AA)** — new ledger commits, "LIVE/RECORDED", run loaded/failed announced via `role="status"` (polite) without moving focus; errors via `role="alert"` sparingly.

## Contrast tooling note
WCAG 2.2 normative contrast is the WCAG 2 ratio (WebAIM checker, axe). APCA is useful for tuning a dark palette perceptually but is **not** a WCAG 2.2 conformance measure — pass the WCAG 2 ratio first.

Content was rephrased for compliance with licensing restrictions.
