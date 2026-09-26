# UI/UX Pro Max — distilled rules for a dark scientific dashboard

Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (`.claude/skills/ui-ux-pro-max/SKILL.md`, `references/quick-reference.md`, MIT)

Content was rephrased for compliance with licensing restrictions.

Optional tool use (Python 3, no deps): `python .claude/skills/ui-ux-pro-max/scripts/search.py "<2-5 terms>" --domain ux|color|chart|typography` or `--stack react`. For dashboards add `--density 8` to get an 8–32px spacing scale. Never present a zero-result search as data.

## Priority order (work top-down)
1. Accessibility — CRITICAL
2. Interaction/targets — CRITICAL
3. Performance — HIGH
4. Style consistency — HIGH
5. Layout/responsive — HIGH
6. Typography & color — MEDIUM
7. Animation — MEDIUM
8. Forms & feedback — MEDIUM
9. Navigation — HIGH
10. Charts & data — LOW generally, but HIGH for Safe Harbor (genome track, graph, evidence tables)

## Accessibility
- Text contrast ≥ 4.5:1 (large 3:1); focus ring 2–4px and ≥ 3:1 against neighbors.
- Accessible names on icon controls; decorative icons hidden from AT.
- Tab order follows visual order; skip link; heading levels sequential.
- Never convey status by color alone — pair color with text/icon (e.g. reopened/blocked/failed task nodes currently share one amber border; add distinct text or shape).
- Sticky UI/drawers must not cover the focused control (WCAG 2.2).
- Every drag action (graph pan, timeline scrub) needs a single-pointer and keyboard alternative.
- Web pointer targets ≥ 24×24 CSS px (small sequence/timeline buttons at 10px font with 6px padding are borderline — measure).
- Count/status changes announced as a full phrase via one live region, without moving focus.

## Interaction
- Buttons disable + show progress during async work; errors shown next to the cause.
- Hover never the only path; feedback within ~100ms; drag needs a movement threshold.

## Performance
- Reserve space for async content (igv.js/xyflow containers need fixed min-height) to keep CLS < 0.1.
- Virtualize lists > 50 items; debounce resize/scroll; per-frame work < 16ms.
- Skeletons for waits > 1s instead of blank frames.

## Layout
- Systematic breakpoints; defined z-index scale (e.g. 0/10/20/40/100/1000 — repo uses 19/20 ad hoc).
- Avoid nested scroll regions fighting the page; prefer `100dvh` over `100vh` (drawers already use `dvh`).
- Long tokens (hashes, IDs, URLs): `overflow-wrap:anywhere` inside a shrinkable (`min-width:0`) child; never `word-break:break-all` on prose.
- Chips/pills: wrap the collection before shrinking labels; if truncating, expose full text on hover *and* focus.

## Typography & color (dark mode)
- Body line-height 1.5–1.75; consistent scale (12/14/16/18/24/32); body text not below 12px.
- Semantic tokens (`--surface`, `--on-surface`, `--accent`, `--warning`, `--danger`) instead of raw hex in components.
- Dark palettes use desaturated/lighter tonal variants, not inverted light colors; test contrast separately.
- Tabular figures for data columns, coordinates, counters, timers.
- Prefer wrapping over truncation; when truncating provide full text via tooltip/expand.

## Animation
- Transform/opacity only; 1–2 animated elements per view; exits ~60–70% of enter duration.
- Motion must express cause→effect; never block input during animation; must be interruptible.
- Unify duration/easing tokens globally.

## Navigation
- Active location clearly highlighted (breadcrumb `active`, selected candidate).
- Deep links for key states; back restores scroll and filter state.
- Modals/drawers have a clear close and Escape; don't use modals for primary flow.
- After view change, move focus to the new main region for screen readers.

## Charts & data (genome track, pipeline graph, tables)
- Always show a legend near the chart; label axes with units (bp, Mb) and readable ticks.
- Tooltips on hover *and* keyboard focus with exact values.
- Provide a table or text alternative / `aria-label` summary of the key insight.
- Avoid red/green-only encodings; supplement color with pattern/shape; data marks ≥ 3:1 vs background, data text ≥ 4.5:1.
- Gridlines low-contrast; emphasize data over decoration.
- 1000+ points: aggregate/sample with drill-down; keep a clear back-path/breadcrumb for drill-down (chromosome → region → sequence).
- Meaningful empty, loading (skeleton, not empty axes) and error (message + retry) states for every chart.
- Sortable tables expose `aria-sort`; offer CSV/image export for data-heavy views.
- Clearly label time granularity on time-series (timeline replay).
