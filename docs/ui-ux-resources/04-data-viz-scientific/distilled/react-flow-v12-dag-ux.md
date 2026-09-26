# React Flow v12 DAG UX (@xyflow/react 12.12.0)

Sources: https://reactflow.dev/learn/layouting/layouting, https://reactflow.dev/examples/layout/dagre, https://reactflow.dev/examples/layout/elkjs, https://reactflow.dev/learn/advanced-use/performance, https://reactflow.dev/learn/advanced-use/accessibility, https://reactflow.dev/api-reference/types/fit-view-options, https://github.com/dagrejs/dagre, https://github.com/kieler/elkjs

*Content was rephrased for compliance with licensing restrictions.*

## What `Graph.tsx` does today (checked 2026-09-26)
- It uses `fitView` with `fitViewOptions={{padding:0.08,minZoom:.45,maxZoom:1}}`, `nodesDraggable={false}`, and a `key` that forces a full remount on every filter toggle.
- A capture-phase `onKeyDown` handler maps Enter/Space to selection.
- Fixer implications:
  - The `fitView` *prop* only runs on first render. After nodes change without a remount, call `useReactFlow().fitView({ padding, duration })` yourself, after layout.
  - Remounting via `key` resets the viewport and focus. That is acceptable, but focus has to go back to a sensible element afterwards.

## Auto-layout
- **dagre** is the recommended default for task/evidence trees and DAGs. It is synchronous and fast, with little configuration. Set `rankdir: 'LR'` so the left-to-right stages (Screen → Investigate → Compare → Review → Report) line up with the `.stage-labels` header. Use `nodesep`/`ranksep` for spacing. dagre needs each node's width and height: use `node.measured` (v12) once nodes are measured, or fixed sizes per node type.
- A known dagre limitation: sub-flow layout breaks when a child node connects to something outside its group. If evidence nodes live in groups, lay the groups out yourself or use ELK.
- **elkjs** is async, highly configurable, and supports ports, compound nodes and edge routing. It is large, so lazy-load it. The React Flow team warns it is hard to support, so use it only if dagre truly isn't enough.
- **d3-force** is iterative and wrong for a dependency DAG, whose direction carries meaning. Avoid it.
- Keep layout deterministic: sort nodes and edges by a stable id before layout, so a replay at time *t* always looks identical.
- Pin stages to columns: give each node a `rank` constraint, or compute `x` from the stage index and let dagre compute only `y`.

## Node status styling (ties to the honesty rules)
- Every node shows at least: its status as **text** (not colour alone), an icon, and a border style. Suggested encodings:
  - complete = solid border
  - running = animated/dashed border, turned off under `prefers-reduced-motion`
  - blocked/failed = distinct icon and label
  - not-started/missing = hollow or greyed, labelled "not run"
- **Never style a missing-evidence node like a negative or failed result.** "No evidence yet" is its own neutral state.
- Evidence edges: use solid lines for recorded dependencies. If inferred or planned edges are ever shown, draw them dashed and include that in the legend.
- Render a small legend inside the panel. React Flow has no built-in legend.

## Accessibility (built-in props)
- Nodes and edges can take keyboard focus by default: `nodesFocusable`, `edgesFocusable`, `disableKeyboardA11y`. Tab moves between elements, Enter/Space selects, Escape deselects. `autoPanOnNodeFocus` scrolls the focused node into view.
- The default node role is `group`. Override it per node with `ariaRole`, and add attributes with `domAttributes` (e.g. `aria-label: "Task: liftover check — complete, 3 evidence records"`). If the node contains a real button, put the button role on that element, not on the wrapper.
- `ariaLabelConfig` lets you replace the built-in instruction strings. Because this graph is read-only (`nodesDraggable={false}`), remove the "press delete to remove / arrows to move" wording.
- Always provide a non-canvas alternative: a list or table of tasks and evidence that screen-reader users (and the test suite) can use.

## Performance
- Custom `nodeTypes`/`edgeTypes` must be defined at module level or wrapped in `React.memo`. The same goes for callbacks passed to `<ReactFlow>` (`useCallback`) and objects/arrays passed to it such as `fitViewOptions` and `defaultEdgeOptions` (`useMemo`). Inline object literals cause re-renders.
- Don't subscribe components to the whole `nodes` array. Keep derived data, such as selected ids, in its own store field.
- For big graphs, collapse subtrees with `node.hidden` and keep node CSS cheap: no heavy shadows, gradients or infinite animations on many nodes.
- During timeline playback, update only `data`/`className` on the affected nodes. Don't rebuild and re-lay out the whole graph on every tick.
