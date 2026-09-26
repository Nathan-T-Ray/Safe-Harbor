# Loading / Empty / Error State Patterns

Sources: [NN/g — Response Times: The 3 Important Limits](https://www.nngroup.com/articles/response-times-3-important-limits/) · [NN/g — Skeleton Screens 101](https://www.nngroup.com/articles/skeleton-screens/) · [Carbon — Empty states pattern](https://carbondesignsystem.com/patterns/empty-states-pattern/) ([repo](https://github.com/carbon-design-system/carbon), Apache-2.0) · [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) · [shadcn/ui](https://github.com/shadcn-ui/ui) (Skeleton/Alert/Empty compositions, MIT)

Content was rephrased for compliance with licensing restrictions.

## Timing thresholds (NN/g)
| Duration | User perception | What to show |
|---|---|---|
| < 0.1 s | Instant | Nothing extra; just the result. |
| 0.1–1 s | Noticeable, but flow is kept | Usually nothing. Don't flash a spinner (use the IG-I5 delay). |
| 1–10 s | Attention starts to wander | Spinner on the affected module, or a skeleton for full-panel loads. |
| > 10 s | User leaves mentally | Progress bar with percent or steps done, **plus a Cancel control**. Expect users to need to reorient on return. |

Safe-Harbor runs, replays, and genome loads can take longer than 10 s. Show named stages ("Evaluating candidate 3/8…") and a cancel/stop action.

## Loading (ST-L)
- **ST-L1** Use skeletons only for panel or full-view loads, and make them match the final layout exactly (same heights) to avoid layout shift. Don't use a "frame-only" skeleton with no content shapes.
- **ST-L2** Use spinners for single modules (a graph panel, the igv track, one card). Keep the module's frame and title visible.
- **ST-L3** For determinate processes (uploads, multi-step runs), use a progress bar, not a skeleton.
- **ST-L4** Put the animation (skeleton shimmer, spinner) behind `prefers-reduced-motion`, falling back to a static tint. Set `aria-busy="true"` on the loading region, and put a visually hidden "Loading …" in the live region.
- **ST-L5** Loading buttons keep their label and get a spinner. Disable them only while the request is in flight.
- **ST-L6** Keep stale data visible (dimmed, or with an "Updating…" badge) during a refresh instead of blanking the panel.

## Empty (ST-E) — three types (Carbon)
| Type | Example here | Content |
|---|---|---|
| No data yet (first use) | No runs, no evidence, empty timeline | Positive title ("Start a run to see evidence"), one sentence on what will appear, a primary action. |
| User-action result | Filter or search returns nothing; a run finished with 0 findings | Say *why* it's empty, and offer "Clear filters" or a way to adjust. |
| Error/permission/config | Backend offline, missing data version | Explain the problem, then the fix (see below). |
- **ST-E1** Show the empty state *in place*, inside the panel or drawer that has no data, at that panel's size. Don't redirect to a page.
- **ST-E2** Keep it short: title, one line of body, at most one primary and one secondary link. Illustrations are optional; skip them in dense dashboard tiles.
- **ST-E3** Design sparse (1–2 items) and dense (hundreds) states too. Check scroll, truncation, and virtualization (`content-visibility: auto` is dependency-free).

## Error (ST-X)
- **ST-X1** Put the error where it happened: field → inline; panel → in the panel; whole app → a banner. Keep the rest of the UI usable.
- **ST-X2** The copy says what happened, why (if known), and how to recover. Offer an action (Retry, Reload data, Open logs), not just "Error".
- **ST-X3** Don't show raw stack traces or JSON by default. Put them behind a "Details" `<details>` with copy-to-clipboard.
- **ST-X4** Announce errors: `role="alert"` for blocking ones, polite `aria-live` for background failures. Don't rely on red alone.
- **ST-X5** Add React error boundaries per major panel (Graph, Genome, Timeline, Inspector), so an igv.js or xyflow crash degrades that one panel with a retry, not the whole app.
- **ST-X6** Timeouts are a first-class state: "Still working… (45 s)" with Cancel, then a distinct timed-out message. (The repo already has timeout E2E artifacts to test against.)
- **ST-X7** Blocked/forbidden states (e.g. the harness drawer "blocked") explain which precondition failed and how to satisfy it.

## Minimal plain-CSS primitives to add (no new deps)
```css
.skeleton{background:var(--surface);border-radius:var(--radius-sm);animation:sk 1.4s ease-in-out infinite}
@keyframes sk{50%{opacity:.55}}
@media (prefers-reduced-motion:reduce){.skeleton{animation:none}}
.state{display:grid;place-items:center;gap:var(--space-2);padding:var(--space-8);text-align:center;color:var(--muted)}
.state h3{color:var(--text);font-size:var(--text-md)}
```
A shared React `<PanelState kind="loading|empty|error" title action />` keeps all panels consistent.
