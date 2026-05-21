<script lang="ts">
/**
 * Shared vertical resize handle for sidebars.
 *
 * Use as a child of a `position: relative` aside. The handle is `position:
 * absolute` and snaps to either the left or right edge depending on `side`.
 *
 * State (`width`, `min`, `max`) is owned by the parent and bound through —
 * this component just emits drag deltas. Window mousemove/mouseup listeners
 * are wired internally so consumers don't repeat that boilerplate.
 */
type Props = {
  /** Which edge the handle clings to. Left handle = drag-left shrinks. */
  side: 'left' | 'right';
  /** Current width, bound from parent. */
  width: number;
  /** Bounds — parent decides clamp range. */
  min: number;
  max: number;
  /** Hide on narrow viewports (matches the existing max-md:hidden treatment). */
  hideOnMobile?: boolean;
};
let { side, width = $bindable(), min, max, hideOnMobile = false }: Props = $props();

let resizing = $state(false);
let startX = 0;
let startW = 0;

function onStart(ev: MouseEvent) {
  if (ev.button !== 0) return;
  ev.preventDefault();
  resizing = true;
  startX = ev.clientX;
  startW = width;
}

function onMove(ev: MouseEvent) {
  if (!resizing) return;
  // Right-anchored handle widens when dragged LEFT (so `startX - clientX`),
  // left-anchored handle widens when dragged RIGHT.
  const delta = side === 'right' ? startX - ev.clientX : ev.clientX - startX;
  const next = startW + delta;
  width = Math.max(min, Math.min(max, next));
}

function onEnd() {
  resizing = false;
}
</script>

<svelte:window onmousemove={onMove} onmouseup={onEnd} />

<!-- Mouse-only resize control; the aria role + label cover the a11y angle. -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
  role="separator"
  aria-orientation="vertical"
  aria-label="Resize sidebar"
  class="resize-handle absolute top-0 z-10 flex h-full w-3 cursor-ew-resize items-center justify-center"
  class:active={resizing}
  class:-left-1.5={side === 'left'}
  class:-right-1.5={side === 'right'}
  class:max-md:hidden={hideOnMobile}
  onmousedown={onStart}
>
  <span class="grip" aria-hidden="true"></span>
</div>

<style>
  .resize-handle .grip {
    width: 2px;
    height: 28px;
    border-radius: 2px;
    background: var(--border-strong, rgba(255, 255, 255, 0.22));
    transition: background-color 120ms ease, height 120ms ease;
  }
  .resize-handle:hover .grip {
    background: var(--primary, #818cf8);
    height: 56px;
  }
  .resize-handle.active .grip {
    background: var(--primary, #818cf8);
    height: 100%;
  }
</style>
