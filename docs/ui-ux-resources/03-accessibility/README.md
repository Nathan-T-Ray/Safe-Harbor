# 03 — Accessibility (a11y) resources for fixing the Safe Harbor UI

**Purpose.** Curated, verified references for AI sub-agents fixing accessibility in `frontend/` (React 19 + Vite + TS, dark theme, plain CSS, custom drawers/pills/toggles, timeline scrubber, `@xyflow/react` task graph, igv.js genome browser, presentation mode with camera-follow auto-scroll). **Testing policy: E2E only (Playwright). Do not add unit/component tests.** Existing E2E scripts are plain Node `.mjs` / Python files in `e2e/safe_harbor/` that import `chromium` from `frontend/node_modules/playwright`.

Metadata verified 2026-09-26 via `gh api repos/{owner}/{repo}` and `npm view`. Stars/last push are GitHub values; "—" = not a GitHub repo (spec/doc page, HTTP 200 verified).

| Name | URL | Stars | Last push | License | What it gives an agent | Relevance |
|---|---|---|---|---|---|---|
| WAI-ARIA APG (w3c/aria-practices) | https://github.com/w3c/aria-practices · https://www.w3.org/WAI/ARIA/apg/patterns/ | 1,353 | 2026-09-24 | W3C (NOASSERTION) | Canonical keyboard + role/state contracts per widget | High |
| APG Dialog (Modal) | https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ | — | — | W3C | Focus-in, Tab wrap, Escape, focus-return rules for drawers | High |
| APG Disclosure | https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/ | — | — | W3C | `aria-expanded` + `aria-controls` for collapsible panels | High |
| APG Button (toggle) | https://www.w3.org/WAI/ARIA/apg/patterns/button/ | — | — | W3C | `aria-pressed` toggle semantics (candidate list, Follow) | High |
| APG Slider | https://www.w3.org/WAI/ARIA/apg/patterns/slider/ | — | — | W3C | Arrow/Home/End/PageUp keys, `aria-valuetext` (media-seek example ≈ timeline) | High |
| APG Toolbar | https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/ | — | — | W3C | Roving tabindex for playback control groups | Med |
| APG Listbox | https://www.w3.org/WAI/ARIA/apg/patterns/listbox/ | — | — | W3C | Alternative to toggle-button list for single-select candidates | Med |
| APG Tabs | https://www.w3.org/WAI/ARIA/apg/patterns/tabs/ | — | — | W3C | If drawer sections become tabs | Med |
| APG Tree View | https://www.w3.org/WAI/ARIA/apg/patterns/treeview/ | — | — | W3C | Text-alternative structure for the task graph | Low |
| WCAG 2.2 (Recommendation) | https://www.w3.org/TR/WCAG22/ | 1,501 (w3c/wcag) | 2026-09-25 | W3C | Normative success criteria; new-in-2.2 list (2.4.11, 2.5.7, 2.5.8 …) | High |
| WCAG 2.2 Quick Reference | https://www.w3.org/WAI/WCAG22/quickref/ | — | — | W3C | Filterable SC + techniques + failures | High |
| Understanding 2.3.3 Animation from Interactions | https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html | — | — | W3C | Rationale for reduced-motion on camera-follow | High |
| MDN `prefers-reduced-motion` | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion | — | — | CC-BY-SA | Media query semantics; panning/scaling are vestibular triggers | High |
| MDN ARIA live regions | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions | — | — | CC-BY-SA | `aria-live`/`role=status` for streaming ledger commits | High |
| axe-core | https://github.com/dequelabs/axe-core | 7,559 | 2026-09-23 | MPL-2.0 | Rules engine (v4.13.0); tags `wcag2a`,`wcag2aa`,`wcag22aa` | High |
| @axe-core/playwright (axe-core-npm) | https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright | 725 | 2026-09-19 | MPL-2.0 | `AxeBuilder({page}).withTags().include().exclude().analyze()` in E2E | High |
| Playwright (emulateMedia, ARIA snapshots, a11y testing guide) | https://github.com/microsoft/playwright · https://playwright.dev/docs/accessibility-testing · https://playwright.dev/docs/aria-snapshots | 96,706 | 2026-09-26 | Apache-2.0 | `page.emulateMedia({reducedMotion:'reduce'})`, `getByRole`, `ariaSnapshot()` | High |
| React Flow accessibility | https://reactflow.dev/learn/advanced-use/accessibility · https://github.com/xyflow/xyflow | 38,501 | 2026-09-24 | MIT | `nodesFocusable`, `ariaRole`, `domAttributes`, `ariaLabelConfig`, `autoPanOnNodeFocus` | High |
| pa11y | https://github.com/pa11y/pa11y | 4,558 | 2026-09-21 | LGPL-3.0 | CLI URL scanner (v10.0.0; axe/htmlcs runners) — secondary cross-check | Low |
| pa11y-ci | https://github.com/pa11y/pa11y-ci | 635 | 2026-09-13 | LGPL-3.0 | Multi-URL CI runner | Low |
| eslint-plugin-jsx-a11y | https://github.com/jsx-eslint/eslint-plugin-jsx-a11y | 3,619 | 2026-01-06 | MIT | Static JSX lint (v6.10.2); not a test, optional hygiene | Med |
| Lighthouse | https://github.com/GoogleChrome/lighthouse | 30,819 | 2026-09-20 | Apache-2.0 | Accessibility score (axe subset) for a quick audit | Low |
| A11Y Project checklist | https://www.a11yproject.com/checklist/ · https://github.com/a11yproject/a11yproject.com | 3,893 | 2026-08-31 | Apache-2.0 | Plain-language WCAG checklist | Med |
| focus-trap | https://github.com/focus-trap/focus-trap | 1,562 | 2026-09-23 | MIT | Robust trap (v8.2.2) if `dialogFocus.ts` proves insufficient | Med |
| focus-trap-react | https://github.com/focus-trap/focus-trap-react | 784 | 2026-09-23 | MIT | React wrapper (v12.0.3) | Low |
| react-focus-lock | https://github.com/theKashey/react-focus-lock | 1,391 | 2026-09-26 | MIT | Alternative React focus lock (v2.13.7) | Low |
| WebAIM Contrast Checker | https://webaim.org/resources/contrastchecker/ | — | — | WebAIM | WCAG 2 ratio checks (4.5:1 text, 3:1 UI/large) | High |
| APCA (Myndex/apca-w3, SAPC-APCA) | https://github.com/Myndex/apca-w3 · https://git.apcacontrast.com/ | 212 / 586 | 2026-05-06 / 2026-07-25 | Custom "Limited W3" | Perceptual contrast for dark themes — advisory only, not WCAG 2.2 normative | Low |
| React Spectrum / React Aria | https://github.com/adobe/react-spectrum | 15,890 | 2026-09-26 | Apache-2.0 | Reference implementations (slider, toolbar, FocusScope) to read, not adopt | Low |

Excluded: `GoogleChrome/accessibility-developer-tools` (archived), `WICG/inert` polyfill (native `inert` is baseline; last push 2024).

## How a fixer agent should use these

1. Start with `distilled/aria-patterns-for-this-ui.md` to find the pattern for the component you are touching; open the APG page only if you need detail.
2. Check your change against `distilled/wcag-2.2-checklist-for-dashboards.md` (contrast, focus visible/not obscured, target size, status messages).
3. Anything moving (camera-follow, cue animations, smooth scroll) → `distilled/reduced-motion-and-auto-scroll.md`. Note `cues.ts` already has `prefersReducedMotion()`; extend it, don't duplicate.
4. Prove the fix with an E2E script per `distilled/axe-playwright-e2e-recipe.md` (axe scan + keyboard assertions + reduced-motion emulation). No unit/component tests.
5. Prefer native HTML (`<button>`, `<input type="range">`, `inert`) over ARIA; only add a library (focus-trap) if the existing `useDialogFocus` can't be fixed.
6. Automated scanners catch only a portion of issues (not focus order, focus return, or meaningful labels); always add explicit keyboard-path assertions.

## Distilled files

- `distilled/wcag-2.2-checklist-for-dashboards.md`
- `distilled/aria-patterns-for-this-ui.md`
- `distilled/reduced-motion-and-auto-scroll.md`
- `distilled/axe-playwright-e2e-recipe.md`
