# Live design-review workflow (OneRedOak) — distilled

Source: https://github.com/OneRedOak/claude-code-workflows/tree/main/design-review (`design-review-agent.md`, `design-principles-example.md`, MIT). Tooling: https://github.com/microsoft/playwright-mcp

Content was rephrased for compliance with licensing restrictions.

Principle: judge the running app first, code second. In this repo use the existing Playwright (`frontend/`, v1.63) if no Playwright MCP is available.

## Phases
0. **Prep** — read the change description/diff; start the dev server; viewport 1440×900.
1. **Flow & interaction** — run the main path (select candidate → inspect genome → open evidence/inspector drawer → timeline replay → export). Exercise hover, active, disabled; confirm destructive actions ask first; note perceived latency.
2. **Responsive** — screenshot at 1440, 768 (repo breakpoints: 1200/960/650), 375. No horizontal scroll, no overlap, no clipped controls.
3. **Visual polish** — alignment and spacing consistency, type hierarchy, palette consistency, eye lands on the conclusion first.
4. **Accessibility (WCAG 2.1 AA)** — full Tab order, visible focus everywhere, Enter/Space activate, semantic HTML, labels, alt text, contrast ≥ 4.5:1 for text.
5. **Robustness** — invalid input (bad run ID), overflow (long gene names, hashes, 100+ evidence rows), loading/empty/error states.
6. **Code health** — reuse existing classes/components, use tokens (CSS vars) not magic numbers, follow existing patterns.
7. **Content & console** — proofread strings; zero console errors/warnings.

## Reporting rules
- Describe the problem and user impact, not a pixel prescription (fixer agents may then choose the fix, but must justify it).
- Triage every finding: **Blocker** (must fix now) · **High** (fix before merge) · **Medium** (follow-up) · **Nit:** (cosmetic).
- Attach a screenshot for every visual finding; open with what works.

Report skeleton:
```
### Design Review Summary
### Findings
#### Blockers
#### High-Priority
#### Medium-Priority / Suggestions
#### Nitpicks
```

## Dashboard checklist items relevant to Safe Harbor (from the principles file, adapted)
- Tokens: neutral ramp of 5–7 grays; semantic colors for success / error / warning / info; verify AA contrast for every pair in the dark palette.
- Type scale with fixed steps (e.g. H1 ~32, body 14–16) and a small set of weights; body line-height ~1.5.
- Spacing on an 8px base (4/8/12/16/24/32); a few consistent radii (small for controls, larger for panels).
- Every component has default/hover/active/focus/disabled states.
- Micro-interactions 150–300ms with ease-in-out/ease-out; skeletons for page loads, spinners for in-component actions.
- Tables: left-align text, right-align numbers, clear headers, adequate row height, sortable headers with indicators, sticky header for long tables.
- Status via color-coded badges *plus* text (live/recorded pills already do this).
- Progressive disclosure for advanced details (criteria, raw records) — keep behind `<details>`/tabs.
