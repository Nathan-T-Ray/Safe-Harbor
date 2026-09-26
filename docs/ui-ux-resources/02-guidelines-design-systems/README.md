# 02 — UI/UX Guidelines, Heuristics & Design-System References

**Purpose.** A verified shortlist of guideline docs, heuristics, color/type systems and accessible-primitive libraries that fixer agents can consult when improving the Safe-Harbor frontend (`frontend/src/safe-harbor/`: React 19 + Vite + TS, dark theme, hand-written CSS in `styles.css` / `presentation.css`, no component library). The `distilled/` checklists are the fast path; this table is for going deeper.

Verified 2026-09-26: repo stats via `gh api repos/{owner}/{repo}` (stars, `pushed_at`, `license.spdx_id`); web pages via direct fetch. "NOASSERTION"/"none" = GitHub could not detect a standard license — check the repo before copying code. Web-only resources show "—".

## Resource table

| Name | URL | Stars | Last push | License | What it gives an agent | Relevance |
|---|---|---|---|---|---|---|
| Vercel Web Interface Guidelines | https://github.com/vercel-labs/web-interface-guidelines | 903 | 2026-08-18 | MIT | A concrete, lint-like checklist covering focus, forms, animation, layout, content, dark-mode `color-scheme`, and tabular numbers. Also ships an AGENTS.md | High |
| Nielsen Norman — 10 Usability Heuristics | https://www.nngroup.com/articles/ten-usability-heuristics/ | — | — | © NN/g | A standard vocabulary for classifying UX findings, e.g. H1 "visibility of system status" | High |
| NN/g — Response time limits (0.1 s / 1 s / 10 s) | https://www.nngroup.com/articles/response-times-3-important-limits/ | — | — | © NN/g | Timing thresholds that tell you when to show a spinner vs. a progress bar vs. a cancel control | High |
| NN/g — Skeleton screens 101 | https://www.nngroup.com/articles/skeleton-screens/ | — | — | © NN/g | Guidance on choosing skeletons, spinners, or progress bars | Med |
| W3C WAI-ARIA Authoring Practices (APG) | https://github.com/w3c/aria-practices · https://www.w3.org/WAI/ARIA/apg/patterns/ | 1,353 | 2026-09-24 | W3C (NOASSERTION) | The reference keyboard/focus/ARIA contract for dialogs, tabs, toolbars, sliders, and grids | High |
| Carbon Design System (IBM) | https://github.com/carbon-design-system/carbon · https://carbondesignsystem.com/patterns/empty-states-pattern/ | 9,495 | 2026-09-26 | Apache-2.0 | A dense data-dashboard system with a gray-100 dark theme, plus empty/loading/notification patterns | High |
| Radix Colors | https://github.com/radix-ui/colors · https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale | 1,676 | 2025-12-17 | MIT | A 12-step scale where each step has a defined role (bg / hover / border / text). Dark scales can be copied as plain CSS vars | High |
| APCA (SAPC-APCA) | https://github.com/Myndex/SAPC-APCA · https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell | 586 | 2026-07-25 | NOASSERTION | A perceptual contrast method with Lc thresholds by font size/weight that holds up on dark UIs where WCAG 2 ratios mislead | High |
| apca-w3 (JS lib) | https://github.com/Myndex/apca-w3 | 212 | 2026-05-06 | NOASSERTION | An `APCAcontrast()` function you can call in a Node script or test to audit token pairs | Med |
| Open Props | https://github.com/argyleink/open-props | 5,527 | 2026-08-11 | MIT | Ready-made CSS custom-property scales (size, font, shadow, easing, radius) you can copy without a build step | High |
| axe-core | https://github.com/dequelabs/axe-core | 7,559 | 2026-09-23 | MPL-2.0 | Automated a11y rules. Through `@axe-core/playwright` it fits the existing Playwright E2E, so it's a justified devDependency | High |
| Radix Primitives | https://github.com/radix-ui/primitives | 19,334 | 2026-08-08 | MIT | Pattern reference for Dialog, Popover, Tooltip, and Tabs behavior (focus scope, dismiss layers). Read their source; you don't need to install it | High |
| React Aria (react-spectrum) | https://github.com/adobe/react-spectrum | 15,890 | 2026-09-26 | Apache-2.0 | Hooks-level a11y behavior plus its docs' interaction notes (press, focus ring, overlays, `useFocusRing`) | Med |
| Base UI | https://github.com/mui/base-ui | 11,002 | 2026-09-26 | MIT | Unstyled primitives (Dialog, Drawer, Popover). Useful as a reference for data attributes like `data-open` / `data-starting-style` | Med |
| Ariakit | https://github.com/ariakit/ariakit | 8,626 | 2026-09-26 | none detected | Composite widgets (toolbar, composite roving focus) that suit the graph/timeline controls | Med |
| shadcn/ui | https://github.com/shadcn-ui/ui | 124,626 | 2026-09-24 | MIT | Readable component compositions (Sheet = drawer, Skeleton, Empty, Alert). Borrow the markup and CSS ideas, not Tailwind | Med |
| Primer Primitives (GitHub) | https://github.com/primer/primitives | 410 | 2026-09-09 | MIT | Mature dark / dark-dimmed / high-contrast token sets, a good reference for navy-dark neutrals | Med |
| Adobe Leonardo | https://github.com/adobe/leonardo | 2,149 | 2026-07-08 | Apache-2.0 | Generates palettes from target contrast ratios, useful for re-deriving `--muted` and `--line` | Med |
| Evil Martians Harmony | https://github.com/evilmartians/harmony | 249 | 2026-07-25 | MIT | OKLCH palette with consistent APCA contrast per step, delivered as CSS vars | Med |
| Utopia (fluid type/space) | https://utopia.fyi/type/calculator/ | — | — | web tool | Generates `clamp()` type and space steps (`--step-0` …). Replaces ad-hoc px sizes | Med |
| Tailwind CSS (palette ref) | https://github.com/tailwindlabs/tailwindcss | 97,693 | 2026-09-25 | MIT | The slate/zinc palette and spacing scale (4px base) as a sanity reference. Don't add Tailwind | Low |
| Style Dictionary | https://github.com/style-dictionary/style-dictionary | 4,833 | 2026-09-20 | Apache-2.0 | Token build tool. Only worth it if tokens must go to several platforms; overkill here | Low |
| Awesome Design Tokens | https://github.com/sturobson/Awesome-Design-Tokens | 1,299 | 2026-02-20 | Unlicense | Index of token articles and tools | Low |
| Awesome Design Systems | https://github.com/alexpate/awesome-design-systems | 26,018 | 2026-04-28 | Unlicense | Index of public design systems for finding precedents | Low |
| Front-End Checklist | https://github.com/thedaviddias/Front-End-Checklist | 74,279 | 2026-08-14 | none detected | Pre-ship checklist (HTML, CSS, a11y, performance) | Med |
| Front-End Design Checklist | https://github.com/thedaviddias/Front-End-Design-Checklist | 5,342 | 2024-12-10 | CC0-1.0 | Design-handoff checklist (typography, states, grids) | Low |
| UX Checklist | https://github.com/uxchecklist/uxchecklist.github.io | 960 | 2026-04-22 | GPL-3.0 | Process-level UX checklist | Low |
| The A11Y Project | https://github.com/a11yproject/a11yproject.com | 3,893 | 2026-08-31 | Apache-2.0 | Plain-language a11y checklist and how-tos (e.g. hiding content, focus) | Med |
| Floating UI | https://github.com/floating-ui/floating-ui | 32,751 | 2026-09-23 | MIT | Tooltip and popover positioning, only if hand-rolled popovers clip at viewport edges | Low |
| Vaul (drawer) | https://github.com/emilkowalski/vaul | 8,624 | 2025-10-03 | MIT | Drawer motion and dismissal ideas. Reference only | Low |
| The New CSS Reset | https://github.com/elad2412/the-new-css-reset | 2,334 | 2024-08-24 | MIT | A minimal modern reset, if base styles fight native controls | Low |

Checked but not included: `joelcalifa/awesome-ux`, `utopia-fyi/utopia`, `jxnblk/awesome-design-tokens`, `gpbl/awesome-empty-states` (all returned 404 or an API error).

## Observed hotspots in the current CSS (grep, 2026-09-26)
- **Tiny type:** across `styles.css` + `presentation.css` there are 40 occurrences of `font-size:10px`, 34 of `11px`, 14 of `9px`, and 1 of `8px`. Check these against APCA/size rules (see `distilled/03`).
- **No `color-scheme: dark`:** there are zero occurrences, so native scrollbars, `<select>`, and date inputs render light.
- **Thin a11y coverage:** `:focus-visible` appears 5× + 2×, and there's one `prefers-reduced-motion` block per file. Check that every interactive element (graph nodes, timeline, drawer close) is covered. The good news: no `transition: all` and no `outline: none`.
- **Hand-rolled dialogs:** `role="dialog"` + `aria-modal` in `Harness.tsx`, `Inspector.tsx`, and `Presentation.tsx`. Audit them against `distilled/05`.
- **Few announcements:** `aria-live` is used only in `Presentation.tsx`, so async run status elsewhere isn't announced.
- **Tokens:** `:root` defines `--panel #101c2d`, `--line #253349`, `--muted #97a8bf`, `--cyan #83e6d7`, `--amber #e9b774` on bg `#0a1220` / text `#dce5f3`. The `--shp-*` set in `presentation.css` duplicates these with slightly different values (`--shp-line #27405a`, `--shp-muted #9fb1c8`).

## How a fixer agent should use these
1. **Start with `distilled/`.** Each file is a checklist tailored to this stack. Take one item, grep the CSS/TSX for violations, and fix it.
2. **Cite the rule in your change.** Tag each fix with the checklist ID (e.g. `IG-F3`, `DC-2`) or heuristic (e.g. NN/g H1) so reviewers can trace why you made it.
3. **Keep to plain CSS + React.** Add or extend CSS custom properties in `:root`. Don't add Tailwind, a component library, or token build tools. Primitives libraries are for *reading behavior*, not installing. The only justified new dependency is `@axe-core/playwright` (devDependency) for automated a11y checks in the existing E2E suite.
4. **Verify visually.** Run the Playwright E2E, take a screenshot before and after, and check contrast of any color you change with APCA (`apca-w3`) or apcacontrast.com.
5. **Go deeper only when needed.** Use APG for exact keyboard contracts, Radix Colors step roles for choosing a shade, and Carbon for dense-dashboard empty/loading/notification layouts.
