# Dark Theme Color & Contrast Rules

Sources: [Radix Colors — Understanding the scale](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale) ([repo](https://github.com/radix-ui/colors), MIT) · [APCA in a Nutshell](https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell) ([Myndex/SAPC-APCA](https://github.com/Myndex/SAPC-APCA)) · [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) (Design section) · [Primer Primitives](https://github.com/primer/primitives) · [Adobe Leonardo](https://github.com/adobe/leonardo) · [Evil Martians Harmony](https://github.com/evilmartians/harmony)

Content was rephrased for compliance with licensing restrictions.

## Why WCAG 2 ratios are not enough here
APCA's author notes that WCAG 2.x overstates contrast when one color is near black, so a 4.5:1 pair can still be hard to read on a dark UI. Safe-Harbor's bg `#0a1220` is exactly that case. Check dark pairs with APCA (Lc) as well as WCAG 2 (which remains the legal baseline).

## APCA targets (Bronze simple mode; values are absolute Lc)
| Use | Min Lc | Notes |
|---|---|---|
| Body/paragraph text | 75 (90 preferred) | Lc 75 needs about 18px at 400 weight or 16px at 500. |
| Readable non-body text (labels, table cells, captions) | 60 | Lc 60 needs about 24px/400 or 16px/700. Small text needs *more* Lc, not less. |
| Large/bold headings, fine outline icons | 45 | |
| Placeholder, disabled, "spot-readable" text | 30 | |
| Dividers, non-semantic borders, thick focus outlines | 15 | Treat anything under 15 as invisible. |

**Rule DC-1:** In the 9–11 px sizes used widely here, even Lc 90 doesn't make the text comfortable to read. Raise the size (see `03`) before tuning color. `--muted #97a8bf` at 10px on `#0a1220` is the most likely failure.

## Role-based scale (Radix 12-step model), mapped to CSS vars
Define **one** neutral scale and one or two accent scales in `:root`, then refer to them by role:
| Step | Role | Suggested var |
|---|---|---|
| 1 | App background | `--bg` (#0a1220) |
| 2 | Subtle bg: panels, sidebar, canvas | `--panel` |
| 3 / 4 / 5 | Component bg: rest / hover / active-selected | `--surface`, `--surface-hover`, `--surface-active` |
| 6 | Non-interactive borders and separators | `--line` |
| 7 | Interactive component borders | `--line-strong` |
| 8 | Hovered borders, **focus rings** | `--focus` |
| 9 / 10 | Solid accent / its hover | `--accent`, `--accent-hover` |
| 11 | Low-contrast text (secondary) | `--muted` |
| 12 | High-contrast text | `--text` |

- **DC-2 One source of truth.** `presentation.css` repeats the palette as `--shp-*` with drifted values (`--shp-line #27405a` vs `--line #253349`; `--shp-muted #9fb1c8` vs `--muted #97a8bf`). Merge them into one set, or alias them (`--shp-line: var(--line)`).
- **DC-3 Hover/active/focus raise contrast** compared with the resting state. Never lower it.
- **DC-4 Status colors carry meaning plus a label.** Cyan = ok/active, amber = warning/pending. Add a distinct danger hue (e.g. a red around Lc 60 on bg) and never rely on hue alone (IG-C2).
- **DC-5 Chart/graph series** use a color-blind-safe set. Separate series by lightness, not just hue. Check them with a grayscale screenshot.
- **DC-6 Set `color-scheme: dark`** on `:root` so scrollbars, `<select>`, and autofill match the theme. Also set `<meta name="theme-color" content="#0a1220">` in `index.html`.
- **DC-7 Tint neutrals toward the brand hue.** On navy surfaces, borders and shadows should be navy-tinted, not pure gray or black.
- **DC-8 Elevation in dark mode** comes from lighter surfaces plus a subtle semi-transparent border (e.g. `rgb(255 255 255 / .06)`). Heavy black shadows barely show on a dark background.
- **DC-9 Third-party canvases** (igv.js tracks, @xyflow edges, controls, minimap) must be restyled through their CSS classes or options so no light-theme default slips through.

## Tooling (no runtime deps)
- Spot-check pairs at apcacontrast.com, or run `apca-w3` in a throwaway Node script over the `:root` pairs.
- Use Leonardo or Harmony to regenerate a neutral ramp at target contrasts, then paste the hex/OKLCH values into `:root`.
