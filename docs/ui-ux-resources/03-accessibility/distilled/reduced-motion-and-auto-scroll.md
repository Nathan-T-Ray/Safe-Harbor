# Reduced motion, camera-follow and auto-scroll

Sources: [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion), [Understanding WCAG 2.3.3 Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html), [WCAG 2.2 — 2.2.2 Pause, Stop, Hide](https://www.w3.org/TR/WCAG22/), [Playwright page.emulateMedia](https://playwright.dev/docs/api/class-page#page-emulate-media), [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility).

## Why it matters here
Presentation mode pans/scrolls the view to follow the "camera". MDN notes that scaling or panning large objects are typical vestibular triggers. `prefers-reduced-motion: reduce` signals the user wants non-essential motion removed, reduced, or replaced (e.g. by a fade). WCAG 2.3.3 (AAA) asks that interaction-triggered motion be disable-able; 2.2.2 (A) requires a way to pause/stop auto-moving content lasting over 5 seconds.

## Existing code (don't duplicate)
- `frontend/src/safe-harbor/cues.ts`: `prefersReducedMotion()` and a hook that listens to the media query `change` event; the camera path uses `scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'nearest' })`.
- `presentation.css`: reduced-motion block disables `.shp-cue`, `.shp-story li`, `.sh-cue-highlight` animations/transitions.

## Rules for fixers
1. **Every** smooth scroll / `scrollTo` / `scrollIntoView` / CSS `scroll-behavior: smooth` / transform-based pan goes through the reduced-motion hook. Grep for `behavior:` and `scroll-behavior` after changes.
2. Reduced ≠ nothing: keep the *state change* (the target becomes visible, a highlight appears) but make it instant or a short opacity change.
3. Global CSS safety net (in `styles.css`):
   ```css
   @media (prefers-reduced-motion: reduce) {
     html { scroll-behavior: auto; }
     *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
   }
   ```
   Use `.01ms` rather than `none` so `animationend`/`transitionend` listeners still fire.
4. **User override beats automation.** If the user scrolls, wheels, presses a key, or moves focus manually while follow is on, pause follow (set Follow off, announce "Follow paused" via `role="status"`). Never yank the viewport away from the element holding keyboard focus (also protects WCAG 2.4.11).
5. Follow toggle and Pause must be always visible and keyboard-reachable during presentation (2.2.2).
6. Consider an in-app "Reduce motion" setting that ORs with the OS preference, persisted in `localStorage`.
7. React Flow: when reduced, pass `autoPanOnNodeFocus={false}` or call `fitView`/`setCenter` with `duration: 0`.
8. igv.js locus jumps: jump directly; avoid animated zoom when reduced.
9. Auto-scroll must use `block: 'nearest'` and account for sticky bars (`scroll-margin`/`scroll-padding`) so the followed item isn't hidden under the timeline.

## E2E verification (Playwright)
```js
const context = await browser.newContext({ reducedMotion: 'reduce' });
// or on an existing page: await page.emulateMedia({ reducedMotion: 'reduce' });
const reduced = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
// Assert no running animations on camera-follow targets:
const running = await page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running').length);
check('no running animations under reduced motion', running === 0, { running });
// Assert follow still reaches its target instantly:
// (placeholder selector — use the real active-cue class, e.g. '.sh-cue-highlight')
await page.locator('.sh-cue-highlight').first().waitFor({ timeout: 2000 });
```
Run the same scenario with `reducedMotion: 'no-preference'` to prove smooth behavior still works.

Content was rephrased for compliance with licensing restrictions.
