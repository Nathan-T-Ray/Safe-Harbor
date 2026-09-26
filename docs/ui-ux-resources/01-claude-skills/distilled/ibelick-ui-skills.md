# ibelick ui-skills (`baseline-ui`, `fixing-accessibility`, `fixing-motion-performance`) — distilled

Source: https://github.com/ibelick/ui-skills/tree/main/skills (MIT)

Content was rephrased for compliance with licensing restrictions.

Review mode used by all three skills: for each violation report **the exact offending snippet → one-sentence reason → concrete code fix**. Prefer small targeted fixes; don't rewrite the UI or switch libraries.

Stack note: the originals assume Tailwind + Radix/Base UI + `motion/react`. Safe Harbor uses plain CSS and native elements — apply the *intent* with CSS/native HTML; do not add those libraries.

## baseline-ui (anti-slop baseline)
- Use the project's existing components/classes first; don't mix primitive systems in one surface.
- Don't hand-roll keyboard/focus behavior when a native element (`<dialog>`, `<details>`, `<button>`, `<select>`) provides it.
- Destructive/irreversible actions go through a confirmation dialog.
- Loading = structural skeletons; errors shown where the action happened.
- Use `100dvh` not `100vh`; respect safe-area insets for fixed elements.
- Animation: none unless requested; only `transform`/`opacity`; never width/height/top/left/margin/padding; interaction feedback ≤ 200ms; ease-out for entrances; pause loops off-screen; respect reduced motion.
- Typography: `text-wrap: balance` on headings, `text-wrap: pretty` on paragraphs, tabular numbers for data, truncate/line-clamp in dense UI, don't tweak letter-spacing without reason (repo adjusts tracking widely — only change if asked).
- Fixed z-index scale, no arbitrary values.
- No large animated `blur()`/`backdrop-filter`; `will-change` only during an active animation; don't use `useEffect` for what render logic can compute.
- No gradients/glow as primary affordances; one accent color per view; empty states offer one clear next action; reuse existing color tokens before adding new ones.

## fixing-accessibility (priority order)
1. **Names** — every control named; icon buttons `aria-label`; inputs labeled; meaningful link text; decorative icons `aria-hidden`.
2. **Keyboard** — no div/span buttons; everything reachable by Tab; visible focus; no `tabindex > 0`; Escape closes overlays.
3. **Focus & dialogs** — trap focus in open drawers/modals, set initial focus inside, restore focus to trigger on close, no unexpected page scroll on open. (Check `.inspector-drawer`, `.harness-drawer`.)
4. **Semantics** — native elements over roles; if a role is used, include its required ARIA; lists as `ul/ol>li`; no skipped heading levels; `th` for table headers.
5. **Forms** — errors linked via `aria-describedby`; required announced; `aria-invalid` on bad fields; disabled submit explains why.
6. **Announcements** — `aria-live` for critical errors; `aria-busy` or status text while loading; toasts not the only channel for critical info; expanders use `aria-expanded` + `aria-controls`.
7. **Contrast & states** — sufficient text/icon contrast; hover-only features have keyboard equivalents; disabled not signaled by color/opacity alone (repo uses `opacity:.45` — add cursor/text cue).
8. **Media & motion** — correct alt (meaningful or empty); reduced motion honored.

## fixing-motion-performance
- Never interleave layout reads and writes in one frame; never drive animation from scroll events/`scrollTop`; every `requestAnimationFrame` loop has a stop condition; don't combine multiple systems that each measure layout (watch igv.js + xyflow + React resize handlers).
- Default to transform/opacity; JS animation only when interaction demands it; paint/layout animation only on small isolated elements.
- Measure once then animate (FLIP); batch reads before writes.
- Use IntersectionObserver to pause off-screen work; prefer CSS scroll/view timelines to scroll polling.
- Don't animate CSS variables that feed transform/opacity/position or inherited variables.
- `will-change` briefly and surgically; avoid many/large promoted layers.
- Blur: small (≤ 8px), one-shot, never continuous, never on large surfaces (the drawer scrim's 2px static blur is acceptable; don't animate it).
