# interface-design `/design-review` — distilled craft review

Source: https://github.com/Dammyjay93/interface-design/blob/main/.claude/commands/design-review.md (MIT). Related scoring model: https://github.com/pbakaus/impeccable (`reference/audit.md`, Apache-2.0).

Content was rephrased for compliance with licensing restrictions.

Default is **judge, don't mutate**: produce findings + verdict; rebuild only when asked. Review against the product's own intent (a dense scientific instrument is allowed to be dense).

## Procedure
1. **Scope & intent** — bound what's under review; read any design system notes; state intended user, task, feel.
2. **See the whole** — screenshot first. Does one element lead? Does the layout breathe or is it a uniform grid of boxes? Does it look like *this* product? Squint: does hierarchy survive?
3. **Lenses, one at a time** (test = "decided or defaulted?"):
   - **A Hierarchy** (most valuable): name the focal element (should be the conclusion/verdict); confirm it wins on size/weight/contrast/isolation and that secondary items are actively demoted; three tiers (primary / secondary / metadata) distinguishable without reading.
   - **B Type & color**: hierarchy from size+weight+color together; a real ratio-based scale; ~4-step text color ramp; tabular numbers where values update; one purposeful accent (~10% of surface), color means status/action/identity; surfaces share one hue varying lightness.
   - **C Surfaces & depth**: small elevation steps; low-opacity borders that are findable not loud; one depth strategy (borders *or* shadows, not ad hoc mix); nested radii concentric (outer = inner + padding).
   - **D Composition & rhythm**: density varies deliberately; proportions express relationships (rail 242px vs content); content width considered.
   - **E States, polish, motion**: every control has default/hover/active/focus/disabled; data has loading/empty/error; hit areas ~44px (40 minimum); UI motion < 300ms with ease-out, press feedback, popovers scale from trigger; only transform/opacity; no `transition: all`.
   - **F Structure & content**: no hand-rolled controls where native/primitives exist; hunt CSS hacks (negative margins undoing padding, magic `calc()`, absolute positioning dodging flow); every string tells one coherent story.
4. **Score & filter** — severity **Blocker** (reads broken/generic: no focal point, flat hierarchy, missing states, structural hacks) · **Should-fix** (craft gap, still works) · **Note**. Drop: taste-only preferences, bold choices matching intent, out-of-scope lines, things already ratified by the design system, lint/format issues. If you can't state the user cost, cut it.
5. **Report** — order: hierarchy → type/color → surfaces/composition → states/motion → structure/content. For each: what defaulted, why it hurts, the specific decision that fixes it, severity. End with a verdict.

## Approval bar (all must hold)
Clear focal point surviving the squint test · size+weight+color type hierarchy · restrained meaningful color · quiet consistent layering · rhythmic composition · complete states and sub-300ms purposeful motion · reuse of existing system and accessible native controls · no structural hacks · coherent content · not mistakable for generic AI output.

## Optional numeric score (Impeccable `audit`)
Score 0–4 each: Accessibility, Performance, Responsive, Theming (tokens vs hardcoded hex, dark-mode contrast), Implementation integrity. Total /20 → 18–20 excellent, 14–17 good, 10–13 acceptable, 6–9 poor, ≤5 critical. Useful for before/after comparison of a fix batch.
