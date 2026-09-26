# igv.js integration notes (igv@3.8.9, React 19)

Sources: https://github.com/igvteam/igv.js (README), https://igv.org/doc/igvjs/, the published bundle `https://unpkg.com/igv@3.8.9/dist/igv.esm.js` (read on 2026-09-26), https://github.com/igvteam/igv-reports, https://igv.org/app/, UCSC help https://genome.ucsc.edu/goldenPath/help/hgTracksHelp.html

*Content was rephrased for compliance with licensing restrictions.*

## Current state in Safe-Harbor
`igv` is a dependency, but `frontend/src/safe-harbor/Genome.tsx` does not import it (checked 2026-09-26). If the panel calls itself a "genome browser", either wire up igv.js or relabel it honestly, e.g. "region summary". Do not claim a live browser that isn't there.

## Lifecycle (checked in the 3.8.9 bundle)
- `igv.createBrowser(div, config)` is async and resolves to a `Browser`. It has no idempotency guard.
- `igv.removeBrowser(browser)` calls `browser.dispose()` and removes `browser.root` from the DOM. `removeAllBrowsers()` also exists.
- The browser listens to **`window` resize only**. When a container changes size (drawer opens, rail collapses, presentation mode), call `browser.visibilityChange()`, which re-runs layout. Also call it after a hidden tab or panel becomes visible, because a browser created at width 0 renders blank.

### React 19 StrictMode-safe pattern
StrictMode runs effects twice in development, so the first async create can resolve *after* cleanup has already run. Guard against that:
```tsx
useEffect(() => {
  let cancelled = false;
  let browser: any; let igvMod: any;
  const el = ref.current!;
  import('igv').then(async ({ default: igv }) => {
    igvMod = igv;
    const b = await igv.createBrowser(el, { genome: 'hg38', locus: initialLocus });
    if (cancelled) { igv.removeBrowser(b); return; }   // StrictMode: cleanup already ran
    browser = b; browserRef.current = b;
    b.on('locuschange', onLocus);
  });
  const ro = new ResizeObserver(() => browser?.visibilityChange());
  ro.observe(el);
  return () => { cancelled = true; ro.disconnect(); if (browser) igvMod.removeBrowser(browser); browserRef.current = null; };
}, []); // create once; drive locus via browserRef.current.search(), not by remounting
```
Key points:
- Create the browser **once**. When the selected candidate changes, call `await browser.search('chr8:127,736,588-127,739,371')` (`goto` also exists). Recreating the browser on every selection causes flicker and leaks.
- Lazy-load `import('igv')`: the ESM bundle is about 3 MB.
- Don't re-emit your own locus into `search()` from inside the `locuschange` handler, or you create a feedback loop. Compare against the last value first.

## Config and navigation UX
- `genome: 'hg38'` matches GRCh38. Always show the assembly next to the coordinates, e.g. "GRCh38 chr8:127.7 Mb".
- Useful options: `locus` (a string or an array of strings, for multi-locus side-by-side views), `showCenterGuide`, `showTrackLabels`, `tracks`. Instance methods include `zoomIn()`, `zoomOut()`, `currentLoci()` and `toSVG()`. `toSVG()` is handy for presentation-mode stills and evidence exports.
- Genome ↔ locus zoom: follow UCSC and igv-webapp conventions. That means an editable locus box that accepts `chr:start-end` or a gene symbol, zoom buttons, and a one-click return to the candidate region. Add padding around the region (about ±10–20 %) so the edges of the region stay visible.
- Rail-to-browser sync (the igv-reports pattern): clicking a candidate row moves the browser to that locus and highlights the row. Selection must stay in sync in both directions.
- Loading and failure: igv.js loads tracks over the network. Show a loading state per track. If a track fails to load, show "track unavailable". Never show an empty lane that reads as "no signal".

## Dark UI theming
igv.js has no dark-theme option. Rather than a CSS `filter: invert()` hack (it distorts track colours), use one of:
1. Put igv on a light "canvas card" with its own border inside the dark UI. This is the most honest option and keeps track colours true.
2. Override chrome-only selectors (`.igv-navbar`, `.igv-track-label`, scrollbars) in scoped CSS, and leave track canvases alone.
Check contrast of any overridden text against WCAG AA.
