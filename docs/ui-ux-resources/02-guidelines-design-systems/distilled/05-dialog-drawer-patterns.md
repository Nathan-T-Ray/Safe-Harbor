# Dialog & Drawer Patterns

Sources: [WAI-ARIA APG — Dialog (Modal) pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) ([w3c/aria-practices](https://github.com/w3c/aria-practices)) · [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) · behavior references: [Radix Primitives Dialog](https://github.com/radix-ui/primitives), [Base UI Dialog/Drawer](https://github.com/mui/base-ui), [React Aria overlays](https://github.com/adobe/react-spectrum), [Vaul](https://github.com/emilkowalski/vaul), [shadcn/ui Sheet](https://github.com/shadcn-ui/ui)

Content was rephrased for compliance with licensing restrictions.

**Context:** `Harness.tsx`, `Inspector.tsx`, and `Presentation.tsx` hand-roll `role="dialog"` + `aria-modal`. Audit each one against this list.

## The modal contract (APG)
- **DD-1 Focus moves in on open.** By default it goes to the first focusable element. Exceptions:
  - If the content is long or structured (tables, evidence lists), focus the title or first paragraph with `tabindex="-1"` so screen-reader users can read in order.
  - If the dialog's final action can't be undone (discard, publish), focus the *least destructive* button.
- **DD-2 Tab and Shift+Tab wrap inside the dialog.** Focus never escapes to the page behind.
- **DD-3 Escape closes it.** So does an always-visible close button with `aria-label="Close"`.
- **DD-4 Focus returns to the element that opened it** on close. If that element is gone, focus the next logical element in the workflow.
- **DD-5 Content behind is inert.** Put the `inert` attribute on the app root (or its siblings) while the modal is open, and dim it with a backdrop. `aria-modal="true"` alone does **not** block mouse or keyboard.
- **DD-6 Labelling:** `aria-labelledby` points to the visible title. Use `aria-describedby` only for short descriptions, and omit it for long, structured content.
- **DD-7 Use `role="alertdialog"`** for short, urgent confirmations (e.g. "Discard run?").

## Recommended implementation (no new deps)
Prefer the native **`<dialog>` element + `showModal()`**. It provides top-layer rendering, inertness of the page behind, Esc to close (the `cancel` event), and a `::backdrop` pseudo-element. You still manage returning focus.
```tsx
const ref = useRef<HTMLDialogElement>(null);
useEffect(() => {
  const d = ref.current!; const opener = document.activeElement as HTMLElement | null;
  if (open) d.showModal(); else if (d.open) d.close();
  return () => opener?.focus?.();
}, [open]);
<dialog ref={ref} aria-labelledby="insp-title" onCancel={e => { e.preventDefault(); onClose(); }} className="drawer">…</dialog>
```
```css
dialog.drawer{margin:0 0 0 auto;height:100dvh;max-height:none;width:min(560px,100vw);
  border:0;border-left:1px solid var(--line);background:var(--panel);color:inherit;padding:0;
  overscroll-behavior:contain;transform:translateX(100%);transition:transform .22s ease-out, display .22s allow-discrete, overlay .22s allow-discrete}
dialog.drawer[open]{transform:none}
@starting-style{dialog.drawer[open]{transform:translateX(100%)}}
dialog.drawer::backdrop{background:rgb(4 8 16 / .6)}
@media (prefers-reduced-motion:reduce){dialog.drawer{transition:none}}
```
If you keep a custom `div` dialog instead, you must implement DD-1 through DD-5 yourself: a focus trap on `keydown` Tab, an Esc listener, `inert` on the siblings, and a return-focus ref.

## Drawer-specific rules
- **DD-8 Modal vs. non-modal.** An inspector users read *alongside* the graph should be a **non-modal** side panel: no backdrop, no focus trap, the page stays interactive, Esc/close still work, and focus moves into it when it opens. Use a modal only when the task must be finished or dismissed first (harness config, confirmations).
- **DD-9 Slide from the anchored edge** using `transform` and `opacity` only, about 200–250 ms with ease-out, and honor reduced motion. Set `transform-origin` and direction to match the edge.
- **DD-10 Scroll containment:** set `overscroll-behavior: contain` on the drawer body, and lock body scroll only for modal drawers. Keep the header (title and close) sticky and the body scrollable.
- **DD-11 Width:** `min(560px, 100vw)` on desktop; full-screen under about 640px. Respect `env(safe-area-inset-*)`.
- **DD-12 Deep-link it:** reflect the open drawer and selected entity in the URL (IG-I7) so refresh and Back restore it, and Back closes it.
- **DD-13 Don't stack more than one modal level.** From inside a drawer, open confirmations as an `alertdialog` in the top layer. Esc closes only the topmost layer.
- **DD-14 Unsaved changes:** if the drawer holds edited form state, confirm before closing, whether by Esc, backdrop click, or route change.

## Playwright checks to add
- Open → `expect(page.getByRole('dialog', { name: /…/ })).toBeFocused()` (or a child is focused).
- Press Tab N+1 times → focus is still inside the dialog. Press Esc → the dialog is hidden and the opener is focused.
- With a modal open, clicking a background control doesn't fire.
- Run `@axe-core/playwright` on the open state.
