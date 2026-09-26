# Typography & Spacing Scale Rules

Sources: [Utopia fluid type calculator](https://utopia.fyi/type/calculator/) · [Open Props](https://github.com/argyleink/open-props) (MIT) · [Tailwind CSS spacing/palette](https://github.com/tailwindlabs/tailwindcss) (MIT, reference only) · [APCA in a Nutshell](https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell) · [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)

Content was rephrased for compliance with licensing restrictions.

## Current state (grep, 2026-09-26)
Across the two stylesheets, font sizes are ad hoc: 40× `10px`, 34× `11px`, 14× `9px`, 1× `8px`, and assorted 12/13/17/20–33px and `clamp()` values. There are no type or space tokens. Fonts are DM Sans (UI) and Manrope (display).

## TY — Type rules
- **TY-1 Use a modular scale as tokens.** Add a small scale to `:root` and replace literal sizes with it. This is a dashboard-tuned static scale (ratio about 1.2, base 14px):
  ```css
  --text-2xs: 0.75rem;   /* 12px  – absolute floor: badges, axis ticks */
  --text-xs:  0.8125rem; /* 13px  – captions, meta */
  --text-sm:  0.875rem;  /* 14px  – default UI text, table cells */
  --text-md:  1rem;      /* 16px  – body, drawer prose */
  --text-lg:  1.25rem;   /* 20px  – section headings */
  --text-xl:  1.5rem;    /* 24px  – drawer titles */
  --text-2xl: clamp(1.5rem, 1.1rem + 1.2vw, 2rem); /* page/hero numbers */
  ```
  Utopia can generate a fluid `clamp()` version (`--step--2 … --step-5`) if hero/presentation views need to scale with the viewport. The calculator's link-comment encodes its inputs, so keep it in the CSS.
- **TY-2 Floor of 12px.** Nothing readable goes under 12px. Uppercase micro-labels at 10–11px should become 12px with `letter-spacing: .04em`, weight 500–600. Per APCA, small sizes need much more contrast than large ones, and the current `--muted` doesn't provide it.
- **TY-3 Use at most 5–6 sizes in the app** plus 3 weights (400/500/600). Signal hierarchy with weight and color first, and size second.
- **TY-4 Line height:** about 1.5 for prose, 1.25–1.35 for dense UI, 1.1–1.2 for large headings. Keep measure to about 60–75ch in drawer prose.
- **TY-5 Numbers:** `font-variant-numeric: tabular-nums` on metrics, coordinates, and timers. Monospace only for hashes and IDs.
- **TY-6 Font roles:** Manrope for display and headings only; DM Sans for everything else. Don't mix them within one component. Add `font-display: swap` and preload the font weights actually used.
- **TY-7 Use rem, not px**, for font sizes so browser zoom and user font settings work. Don't disable zoom.

## SP — Spacing rules
- **SP-1 4px base scale** (the same idea as Tailwind/Open Props sizes):
  ```css
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px;
  ```
  Replace one-off paddings and gaps with these. Allow an odd value only for optical ±1px corrections, and comment it.
- **SP-2 Proximity:** space inside a group is smaller than space between groups (e.g. 8px within a card, 16–24px between cards). The ratio matters more than the exact numbers.
- **SP-3 Prefer `gap`** on flex/grid over margins on children.
- **SP-4 Consistent component heights:** controls in a toolbar share one height (e.g. 32px compact / 36px default). Icons align to the text's cap height.
- **SP-5 Radius scale:** `--radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px`. Nested radius = outer radius − padding.
- **SP-6 Borrowing from Open Props:** copy the specific props you need (sizes, easings, shadows) into `:root`. There's no need to install the package.

## Migration recipe for a fixer agent
1. Add the tokens to `:root` in `styles.css`.
2. Map old values to tokens: 8/9/10/11 → `--text-2xs`, 12/13 → `--text-xs`, 17 → `--text-md`, 20–25 → `--text-lg`/`--text-xl`.
3. Replace literals file by file, then run Playwright and compare screenshots. Expect dense panels to need wrapping or truncation fixes after sizes grow.
