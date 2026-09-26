# Projection readability and motion (SH-U14)

Current acceptance: **49/49 checks passed** after integration, with the unchanged external browser journey. Evidence: `artifacts/safe_harbor/pr64-review/readability-final/report.json` and its screenshots. Keyboard dialogs, selected markers, SVG text sizing, conclusion visibility and reduced-motion checks pass. The original failing review below is retained as historical evidence.

Journey: `e2e/safe_harbor/readability.mjs`. It drives a real browser through the Vite proxy to FastAPI and MongoDB at a **1280×720** viewport. Before measuring, it starts a **deterministic operational** run through the UI ("Start investigation"). The graph, stage labels, task statuses and assessments on screen therefore come from the actual ledger. There is no mocked transport, no model call and no biological interpretation.

```sh
# API on 8040 (unique MONGODB_DATABASE) + Vite on 5190 with API_TARGET=http://127.0.0.1:8040
SAFE_HARBOR_UI_URL=http://127.0.0.1:5190 node e2e/safe_harbor/readability.mjs
# → artifacts/safe_harbor/readability/<timestamp>/{report.json, *.png}; exit 1 if any check fails
```

The thresholds were fixed before measuring:

- Critical text must be at least **12 CSS px**. For SVG text this is the *rendered* size: font-size × (rendered width ÷ viewBox width).
- The conclusion must be at least **18 px**.
- Text contrast must be at least **4.5:1** (WCAG AA).

"Critical" means the text a viewer needs to follow the story: candidate names, coordinates and status; the mode label; the live/recorded pill; breadcrumb; status axes; conclusion; still-to-resolve text; the scientific footnote; stage labels; task status, name and question; the legend; the timeline event; SVG axis and gene labels; track headings; sequence coordinates; and footnotes.

Evidence run: `artifacts/safe_harbor/readability/2026-09-26T18-59-11-338Z/` (report.json plus 11 screenshots). The run was `run-5b246dc9706f400d95338ddfe7b2a213` in database `safe_harbor_readability_u14`. **47 checks: 33 pass, 14 fail (8 critical, 4 major, 2 minor).** The ticket's acceptance criterion is **not met**: critical content still depends on microscopic text, and some state is conveyed by colour alone.

## What passes

- **Layout.** No horizontal page scroll at 1280 px.
- **Contrast.** Every critical text group reaches ≥ 4.5:1 in standard, presentation, locus and sequence views. The lowest measured value is 5.93:1.
- **Conclusion size in presentation mode.** The conclusion is 20 px and fully inside the 720 px viewport.
- **Status in words.** Candidate cards ("incomplete screen", "○ Not yet assessed"), the assessment axes, task nodes (icon plus word), the graph legend (icon plus word), the connection state and the LIVE/RECORDED pill all use text, not colour alone. Bases inside the candidate are marked by an underline border as well as colour.
- **Keyboard.** Candidate cards are reachable with Tab and show a visible focus ring (2 px cyan outline). Enter selects a card (`aria-pressed` and the assessment heading update). The zoom breadcrumb is reachable; Enter on "Locus" changes zoom, focus stays in the breadcrumb, and Tab+Enter advances to "Sequence". Genome SVG markers are focusable and operable. Graph task nodes are reachable with Tab. "Inspect evidence" opens the inspector with Enter, Escape closes it, and focus is back on the invoking button.
- **Motion.** With default motion there are no infinite animations. With `prefers-reduced-motion: reduce`, the zoom `arrive` animation is `none`, control transitions are 0 s, and no animations run after a zoom change. A replay step shows RECORDED REPLAY, the event cause and "n / N" as text.
- **Text alternatives.** Genome, chromosome and locus SVGs have `role="img"` and an `aria-label`. The sequence strip has `aria-label="Actual reference sequence"`.
- **Stability.** No uncaught page errors.

## Findings and concrete fixes (for codex-ui; files under `frontend/src/safe-harbor/`)

Severity follows the report: **critical** means it blocks the acceptance criterion; major and minor follow from that.

### F1 — Critical text below 12 px (critical, all views)

Measured at 1280×720 in standard mode. Presentation mode raises only the footnotes, the candidate coordinate and the task text.

| Element | Selector | Measured | Fix (`styles.css`) |
|---|---|---|---|
| Chromosome numbers (SVG) | `.svg-label` in genome view | **7.4 px** rendered (12 px × 0.61 viewBox scale) | Raise `.svg-label` to 19–20px in the 930-wide genome viewBox, or reduce the viewBox width / split into one column so rendered text is ≥ 12 px |
| Gene labels in locus (SVG) | `.svg-gene` | **6.1 px** rendered | `.svg-gene{font-size:18px}` (renders ≈ 12 px), or render gene names as HTML beside the SVG (see F4) |
| Locus/chromosome axis labels (SVG) | `.svg-label` in locus view | 7.3 px | As above |
| Candidate coordinate | `.candidate-coordinate` | 9 px (10 in presentation) | 12px; drop `letter-spacing:-.2px`; allow wrap |
| Task status word | `.task-state` | 9 px | 12px |
| Scientific footnote | `.scientific-footnote` | 9 px (10) | 12px |
| Coordinate footer | `.coordinate-footer` | 9 px | 12px |
| Sequence coordinate labels | `.sequence-label` | 9 px | 12px |
| Candidate status | `.candidate-status` | 10 px | 12–13px |
| Mode label | `.mode-word` | 10 px | 12px |
| LIVE / RECORDED / run status pills | `.pill` | 10 px | 12px |
| Status axis labels | `.status-axes span` | 10 px | 12px |
| Task question | `.task-question` | 10 px (12 in presentation) | 12px in standard as well |
| Status legend | `.graph-footer` | 10 px | 12px |
| Track heading, genome footnote | `.track-heading`, `.genome-footnote` | 10 px | 12px |
| Mode explanation, breadcrumb, status values, still-to-resolve, timeline event, stage labels | `.mode-notice`, `.genome-breadcrumb button`, `.status-axes strong`, `.question-callout p`, `.timeline-event`, `.stage-labels` | 11 px | 12–13px (breadcrumb and stage labels 13px) |

The simplest fix is a minimum type scale: replace every `font-size:9px|10px|11px` on the selectors above with `12px`. The `.presentation` rules should then *scale up* (for example ×1.15), not just patch four selectors. Re-run the journey; the check fails while any listed element is under 12 px.

### F2 — Standard-mode conclusion is 17 px (critical)

`.conclusion-text` is `font:550 17px/1.55`, and the `@media(max-width:1200px)` rule lowers it to 16 px. Presentation mode (20 px) passes. **Fix:** `.conclusion-text{font-size:18px}` or larger at every width, and remove the 16 px override.

### F3 — Stage labels are 11 px and step numbers 9 px (critical / minor)

`.stage-labels{font-size:11px}` and `.stage-labels i{font-size:9px}`. **Fix:** 13px labels and 12px numerals (a 22 px box). They are readable at 10.7:1 contrast but too small for projection.

### F4 — Locus gene names hidden from assistive technology (critical)

The locus `<svg role="img">` has the label "Coordinate-correct annotation view for chr1:…". Because of `role="img"`, the gene `<text>` children (for example "MAGI3 ←") are presentational, and nothing outside the SVG lists them. **Fix (Genome.tsx, locus branch):** extend the `aria-label` with the shown genes and strands, *or* add a visually compact HTML list or `<table>` below the SVG. For example: `<ul className="gene-list" aria-label="Displayed genes">{uniqueFeatures.slice(0,12).map(f=><li>{f.name} ({f.strand==='-'?'minus':'plus'} strand) {f.start+1}–{f.end}</li>)}</ul>`. The table option also fixes F1 for gene labels.

### F5 — Selected genome marker distinguished only by colour and radius (critical)

The genome markers are cyan when selected (`#7ee8dd`, r=7) and amber otherwise (`#dcae67`, r=5). The `aria-label` "Select Pansio-1" does not change with selection. The legend "● Published candidates at actual positions" shows only the cyan dot, although unselected candidates are amber (**minor**, legend mismatch). **Fix (Genome.tsx):** add `aria-pressed={c.candidate_id===selected?.candidate_id}` to each marker `<g role="button">`, and add a visible non-colour cue such as an outer ring stroke or a text label next to the selected marker. The legend should read "● selected candidate · ● other published candidates".

### F6 — Breadcrumb current level not exposed (major)

The active zoom is conveyed by a `.active` class, which gives colour and background only. **Fix (Genome.tsx):** `aria-current={zoom===level?'step':undefined}` on the breadcrumb button.

### F7 — Graph task nodes: Enter does not open the inspector (major)

React Flow nodes receive focus by Tab, but pressing Enter only selects them; `onNodeClick` is mouse-only. **Fix (Graph.tsx):** pass `onSelect` through node `data` and handle `onKeyDown` (Enter/Space) in `TaskNode`. Alternatively, render the node title as a `<button>` that calls `onSelect(task)`. Give the node an accessible name such as `aria-label={`${taskName[task.kind]}, ${task.status}`}`.

### F8 — Evidence dialog does not receive focus (major)

`Inspector` is `role="dialog" aria-modal="true"`, but after opening, focus remains on "Inspect evidence & calculations" behind the scrim. Escape still closes the dialog, and focus is then naturally on the invoker. **Fix (Inspector.tsx / Harness.tsx):** focus the close button (or the dialog heading) on mount with a `useRef` + `useEffect`, keep Tab inside the dialog while it is open, and restore focus to the invoker on close.

### F9 — Presentation mode: graph and stage labels below the fold (major)

At 1280×720 in presentation mode, the graph panel starts at y=1067 and the document height is 1755 px. The stage labels and task graph are never visible together with the conclusion. **Fix:** in `.presentation`, reduce `.genome-canvas` min-height and the intro heading, or move the graph into a second presentation "slide" and state this in the presenter notes. The check requires the stage labels to appear within the first 640 px.

## Limitations

- Font-size and contrast checks use computed styles and a composited background. They do not account for anti-aliasing or projector gamma. Contrast of SVG text uses the SVG container background.
- The keyboard journey tests Tab/Enter/Escape on the key controls. It is not a full screen-reader audit (no NVDA/VoiceOver run), and it does not audit the harness drawer contents.
- Only a deterministic operational run was exercised. Real-model and mock modes were not.
- Motion checks cover CSS animations and transitions and the Web Animations API. React Flow `animated` edges appear only while a task is *running*; the run finished before measurement, so that state was checked only under reduced motion via the global `animation:none!important` rule, not observed live.
- The page imports Google Fonts. When offline, fallback fonts change metrics slightly; sizes in px are unaffected.

Next dependent work: codex-ui applies F1–F9 in `frontend/src/safe-harbor/`, then re-runs `readability.mjs` until it exits 0. SH-Q* final E2Es can include this journey.
