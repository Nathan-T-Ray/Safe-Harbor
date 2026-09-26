# Dense scientific dashboard layout

Sources: Grafana dashboard best practices https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/ (guidance only; Grafana code is AGPL), Grafana Saga https://grafana.com/developers/saga/, Tremor https://tremor.so/ + https://github.com/tremorlabs/tremor, JBrowse 2 docs https://jbrowse.org/jb2/docs/, HiGlass https://docs.higlass.io/, igv-reports https://github.com/igvteam/igv-reports

*Content was rephrased for compliance with licensing restrictions.*

## Principles
- **One question per view.** Grafana's advice: a dashboard should tell a story and move from general to specific. For Safe-Harbor that path runs candidate rail (which region?) → conclusion (what do we know?) → genome and graph (why?) → drawers (raw evidence).
- **Reduce cognitive load.** Every panel needs a title that says what it shows, plus units and assembly. A newcomer should be able to explain a panel without asking.
- **Compare like with like.** Normalise axes and use a consistent scale across candidates. Avoid stacked charts, which hide individual series.
- **Colour carries meaning, and only one meaning.** Keep status colours separate from decorative and track colours.
- **Drill down, don't duplicate.** Details go into drawers linked from the summary rather than being repeated in several panels.

## Layout patterns
- **Master–detail with linked selection** (igv-reports, JBrowse): the rail selects, and every other panel follows. Selection should show in all panels at once: rail row highlight, locus box, graph filter chip.
- **Linked views** (HiGlass/JBrowse): if two views show the same locus, sync them. If they can un-sync, show a lock/unlock control and its state.
- **CSS grid with named areas.** Give panels a `min-width`/`min-height` so canvases (igv, React Flow) never collapse to 0, because they render blank at 0 size. Every resizable canvas needs a ResizeObserver that triggers its relayout.
- **Drawers**: open them *over* or *beside* the content without resizing the canvases on every animation frame. Resize once, when the transition ends. Trap and restore focus (see `dialogFocus.ts`). Esc closes. The drawer title names the record it shows.
- **Density**: base text 13–14 px in panels, `font-variant-numeric: tabular-nums` for coordinates, counts and times, and 4/8 px spacing. Truncate long ids in the middle (`chr8:127,7…9,371`) and put the full value in a `title` or copy button.
- **Status summary strip** (Tremor tracker/badge style): a compact row per candidate showing all three axes as separate chips. Never collapse it into a single traffic light.
- **Empty, loading and error states are first-class**: a skeleton per panel, a specific message, and a retry control. Never leave a blank panel.
- **Presentation mode**: same data, bigger type, fewer controls. Hide editing and debug UI but **keep caveats and provenance links**. It must be usable with a keyboard (arrow keys step through the story) and should respect `prefers-reduced-motion`.

## Quick audit list
- [ ] Every panel has a title, a units/assembly label, and loading, empty and error states.
- [ ] Selection is in sync across rail, genome, graph and conclusion.
- [ ] Canvases survive rail collapse, drawer open, window resize and presentation toggle.
- [ ] Contrast meets WCAG AA on the dark theme. Focus rings are visible on dark backgrounds.
