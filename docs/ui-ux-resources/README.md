# UI/UX resources for fixer agents

This is a curated, verified knowledge base for AI sub-agents that improve or fix the Safe Harbor frontend (`frontend/src/safe-harbor/`). Every GitHub repo listed here was checked with `gh api` on 2026-09-26. Files under `distilled/` are paraphrased checklists adapted to this stack: React 19, plain CSS, a dark scientific dashboard, and E2E-only testing.

## Read in this order
1. **`00-current-ui/README.md`**: the current component map, stable E2E selectors you must not break, domain constraints, and a ranked issue backlog with a pointer to the guide for each issue.
2. The folder that matches your task:

| Folder | Use it for | Start with |
|---|---|---|
| `01-claude-skills/` | Agent skill packs and review workflows (Anthropic frontend-design, Vercel guidelines, design-review agent, ui-ux-pro-max, Impeccable…) | `distilled/vercel-web-interface-guidelines.md`, `distilled/design-review-workflow.md` |
| `02-guidelines-design-systems/` | Heuristics, colour/contrast, type and spacing scales, loading/empty/error states, dialogs and drawers | `distilled/01-interface-guidelines-checklist.md` |
| `03-accessibility/` | WCAG 2.2, ARIA patterns for this UI, reduced motion, axe + Playwright E2E | `distilled/aria-patterns-for-this-ui.md` |
| `04-data-viz-scientific/` | igv.js, React Flow DAG UX, communicating uncertainty and status, dense layout, timeline/replay | `distilled/communicating-uncertainty-and-status.md` |
| `05-audit-tooling/` | Headless review loop, screenshot and pixel-diff recipes, stylelint and CSS analysis, performance | `distilled/agent-ui-review-loop.md` |

## Fixer-agent protocol
1. **Scope:** pick one backlog item from `00-current-ui`. Claim the ticket according to `docs/safe-harbor/CONTRIBUTING.md`. Stay inside `frontend/src/`.
2. **Baseline:** run `npm run build --prefix frontend`. Take screenshots at 1440, 1024 and 390 px following `05-audit-tooling/distilled/agent-ui-review-loop.md`, with servers running in the background only.
3. **Fix:** make the smallest change that resolves the item. Cite the rule ID from the checklist you used (e.g. `IG-F3`, `DC-2`, WCAG `2.4.11`). Use CSS variables in `:root`. Add no new dependencies without the integrator.
4. **Guard:** keep every stable selector and accessible name listed in `00-current-ui`, and never break a domain constraint. Honesty rules come before aesthetics.
5. **Verify:** rebuild, re-run the affected `e2e/safe_harbor/*.mjs` scripts with `SAFE_HARBOR_UI_URL` set, re-take the screenshots, and report measured before/after numbers (axe violations, stylelint counts, pixel diffs). Do not write unit or component tests.
6. **Report:** list changed paths, what works, acceptance evidence, limitations, and the next ticket.

The distilled content was rephrased for compliance with licensing restrictions. Source URLs are listed at the top of each file.
