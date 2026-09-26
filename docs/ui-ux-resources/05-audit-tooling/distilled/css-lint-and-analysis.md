# CSS lint & analysis for hand-written minified CSS

Sources: [stylelint](https://github.com/stylelint/stylelint) · [stylelint-config-standard](https://github.com/stylelint/stylelint-config-standard) · [Project Wallace css-analyzer](https://github.com/projectwallace/css-analyzer) · [Prettier](https://github.com/prettier/prettier) · [PurgeCSS](https://github.com/FullHuman/purgecss) · [Playwright Coverage](https://playwright.dev/docs/api/class-coverage)

Content was rephrased for compliance with licensing restrictions.

Targets: `frontend/src/safe-harbor/styles.css` (~25.7 KB) and `presentation.css` (~6.7 KB). These are lint/analysis checks — allowed under the E2E-only policy. Nothing here adds deps to the repo.

## Setup (outside the repo, persistent)
```bash
T=/projects/sandbox/.uitools; mkdir -p $T
npm i --prefix $T stylelint stylelint-config-standard @projectwallace/css-analyzer prettier purgecss >/dev/null
echo '{"extends":["stylelint-config-standard"]}' > $T/.stylelintrc.json
```

## 1. stylelint
```bash
cd /projects/sandbox/Safe-Harbor/frontend/src/safe-harbor
$T/node_modules/.bin/stylelint --config $T/.stylelintrc.json --config-basedir $T --formatter json styles.css presentation.css > $T/sl.json
node -e "const r=require('$T/sl.json');const c={};for(const f of r)for(const w of f.warnings)c[w.rule]=(c[w.rule]||0)+1;console.log(Object.entries(c).sort((a,b)=>b[1]-a[1]))"
```
**Measured baseline (2026-09-26):** 312 warnings in styles.css, 59 in presentation.css. By rule:
| rule | count | action |
|---|---|---|
| declaration-block-single-line-max-declarations | 276 | **Noise** from the minified style — disable it (`"declaration-block-single-line-max-declarations": null`) |
| no-descending-specificity | 37 | Real: later, weaker selectors may be overridden unexpectedly — inspect when a style "doesn't apply" |
| no-duplicate-selectors | 19 | Real: same selector declared twice; merge carefully (order matters) |
| at-rule-empty-line-before / comment-empty-line-before | 15 | Noise for minified CSS — disable |
| media-feature-range-notation | 10 | Cosmetic (`width<=900px` vs `max-width`) — ignore unless touching the query |
| font-family-no-missing-generic-family-keyword | 6 | Real: add a generic fallback (`sans-serif`/`monospace`) |
| selector-class-pattern / selector-attribute-quotes | 7 | Style only — ignore |
| declaration-property-value-keyword-no-deprecated | 1 | Real: fix |

Recommended agent config: extend standard, null out the stylistic noise above, then report the **delta** before vs after your change (a fix must not add warnings). Use `--fix` only on a scratch copy — the auto-fixer would reformat the minified file into a huge diff.

## 2. Design-token drift — css-analyzer
```js
// $T/wa.mjs  →  node $T/wa.mjs styles.css presentation.css
import { analyze } from '/projects/sandbox/.uitools/node_modules/@projectwallace/css-analyzer/dist/index.js';
import { readFileSync } from 'node:fs';
for (const f of process.argv.slice(2)) { const r = analyze(readFileSync(f,'utf8'));
  console.log(f, JSON.stringify({rules:r.rules.total, colors:r.values.colors.totalUnique, fontSizes:r.values.fontSizes.totalUnique,
    zIndex:r.values.zindexes.totalUnique, important:r.declarations.importants.total, media:r.atrules.media.totalUnique,
    customProps:r.properties.custom.totalUnique, maxSpecificity:r.selectors.specificity.max})); }
```
**Measured baseline:**
| file | rules | unique colors | unique font-sizes | `!important` | media queries | custom props | max specificity |
|---|---|---|---|---|---|---|---|
| styles.css | 357 | 150 | 20 | 5 | 5 | 5 | 0,4,0 |
| presentation.css | 72 | 49 | 9 | 8 | 3 | 6 | 0,2,1 |

Reading: 150 unique colors and 20 font sizes with only ~5 custom properties means the palette/type scale is mostly hard-coded. When fixing, prefer introducing/reusing `--custom-properties` and push these counts **down**; never up. Also inspect `r.values.colors.unique` to find near-duplicate colors to consolidate.

## 3. Readable view of minified CSS
`$T/node_modules/.bin/prettier --parser css < styles.css > $T/styles.pretty.css` — read/grep the pretty copy; edit the real file in its existing style.

## 4. Unused CSS
- **Preferred (runtime, zero install):** Playwright `page.coverage.startCSSCoverage()` during a real E2E journey (recipe in `playwright-screenshot-recipes.md`). Union the used ranges across all journeys/viewports before calling anything dead — rules for drawers, error states and narrow media queries only apply in those states.
- **Static hint:** `$T/node_modules/.bin/purgecss --css styles.css --content '../**/*.tsx' --rejected -o $T/purge` — lists selectors not found as literal strings. Class names built dynamically (template strings, status-derived names) will be false positives; grep `.tsx` before deleting.

## 5. Always finish with
`cd frontend && npm run build` (type check + bundle) and re-run the affected E2E journey.
