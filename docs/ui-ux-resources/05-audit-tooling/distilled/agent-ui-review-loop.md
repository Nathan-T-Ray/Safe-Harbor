# Agent UI review loop (headless, E2E-only)

Sources: [Vite preview options](https://vite.dev/config/preview-options) · [Playwright page.screenshot](https://playwright.dev/docs/api/class-page#page-screenshot) · [OneRedOak design-review agent](https://github.com/OneRedOak/claude-code-workflows/blob/main/design-review/design-review-agent.md) · [Playwright MCP](https://github.com/microsoft/playwright-mcp)

Content was rephrased for compliance with licensing restrictions.

## 0. Ground rules
- E2E only (AGENTS.md). Allowed checks: `npm run build` (runs `tsc --noEmit && vite build`), lint, schema. No unit/component tests.
- UI lane owns `frontend/src/` only. Don't edit `shared/`, root config or `package.json` without the integrator.
- Never run a server in the foreground. Start in background, poll until ready, kill when done.
- Real data path: UI calls `/api/*`, proxied by Vite to `API_TARGET` (default `http://127.0.0.1:8010`). `vite preview` **inherits `server.proxy`**, so preview works the same as dev if the backend is up. If the backend is down, screenshots will show error/empty states — record that honestly, don't mock.

## 1. Build + serve (background)
```bash
cd /projects/sandbox/Safe-Harbor/frontend
npm run build 2>&1 | tail -20                      # type + bundle check; must pass
(npx vite preview --host 127.0.0.1 --port 4173 --strictPort > /projects/sandbox/.uitools/preview.log 2>&1 &) 
for i in $(seq 1 30); do curl -sf http://127.0.0.1:4173/ >/dev/null && break; sleep 1; done
curl -s http://127.0.0.1:4173/api/health || echo "backend not reachable — note in report"
```
Stop later with `pkill -f "vite preview"`. Existing E2E scripts read `SAFE_HARBOR_UI_URL` (default `http://127.0.0.1:5175`); pass `SAFE_HARBOR_UI_URL=http://127.0.0.1:4173`.

## 2. Shoot baseline ("before")
Run a capture script (see `playwright-screenshot-recipes.md`) at widths **1440×900, 1024×768, 390×844**. For each width save: full-page PNG, `scrollWidth` vs viewport (horizontal overflow), console errors, axe violations, ARIA snapshot. Output to `artifacts/ui-review/<ticket>/before/`.

## 3. Critique (look at the PNGs with vision)
Read each PNG with the file-read tool and walk this checklist (condensed from the OneRedOak phases):
1. **Flow** — primary journey works (candidate card → genome zoom → sequence; harness drawer); hover/focus/disabled states exist.
2. **Responsive** — no horizontal scroll, no overlap/clipping at 390; panels reflow at 1024.
3. **Visual polish** — alignment grid, consistent spacing scale, type hierarchy, limited palette, clear primary action.
4. **Accessibility** — Tab order logical, visible focus ring, Enter/Space activate, labels, contrast ≥ 4.5:1 for body text (axe covers much of this).
5. **Robustness** — long names, empty/loading/error states, `incomplete` evidence states render distinctly (domain rule: missing evidence ≠ negative result; never say "globally safe").
6. **Code health** — reuse existing classes / CSS custom properties rather than new magic numbers.
7. **Console** — zero `pageerror`, no warnings spam.

Triage each finding: **Blocker / High / Medium / Nit**. Describe the problem and its user impact, with the screenshot path as evidence.

## 4. Fix
Smallest change in `frontend/src/safe-harbor/*.tsx|*.css`. Re-run `npm run build`. Optionally run stylelint/css-analyzer (see `css-lint-and-analysis.md`) and compare counts before/after.

## 5. Re-shoot ("after") and verify
- Same script, output to `.../after/`.
- Pixel-diff before vs after (recipe in screenshot file) — confirms the change is localized; large unexpected diff areas = regression suspects.
- Re-read the after PNGs; confirm each Blocker/High is resolved.
- Re-run the relevant existing journey(s) in `e2e/safe_harbor/*.mjs` to make sure nothing functional broke.

## 6. Report
Changed paths; what works; evidence (PNG/JSON paths, diff pixel counts, axe/stylelint counts before→after); limitations (e.g. backend unavailable, Chromium-only); next ticket. Then `pkill -f "vite preview"`.

## Alternative: interactive exploration via Playwright MCP
If the host exposes Playwright MCP (`npx @playwright/mcp@latest --headless`), an agent can navigate/click using accessibility snapshots, which is text-based and needs no vision model; add `--caps vision` for screenshot/coordinate tools. Use it for exploration only — the committed evidence must still come from a re-runnable `.mjs` E2E script.
