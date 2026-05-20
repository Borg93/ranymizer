<script lang="ts">
import { X } from 'lucide-svelte';

type Props = { open?: boolean };
let { open = $bindable(false) }: Props = $props();

type Shortcut = { keys: string[]; description: string };
type Group = { title: string; shortcuts: Shortcut[] };

const groups: Group[] = [
  {
    title: 'Tool',
    shortcuts: [
      { keys: ['V'], description: 'Select tool' },
      { keys: ['B'], description: 'Draw tool' },
      { keys: ['Esc'], description: 'Clear selection' },
    ],
  },
  {
    title: 'Boxes',
    shortcuts: [
      { keys: ['Click bar'], description: 'Select' },
      { keys: ['Drag'], description: 'Move' },
      { keys: ['Shift', '+', 'Click'], description: 'Range-select in sidebar' },
      { keys: ['⌘', '+', 'Click'], description: 'Toggle in selection' },
      { keys: ['Del'], description: 'Delete selected' },
      { keys: ['Double-click row'], description: 'Edit text + category' },
    ],
  },
  {
    title: 'Pages',
    shortcuts: [
      { keys: ['←'], description: 'Previous page (no selection)' },
      { keys: ['→'], description: 'Next page (no selection)' },
      { keys: ['PageUp'], description: 'Previous page' },
      { keys: ['PageDown'], description: 'Next page' },
      { keys: ['⌘', '+', '←/→'], description: 'Previous / next (with selection)' },
    ],
  },
  {
    title: 'Zoom',
    shortcuts: [
      { keys: ['+', '/', '='], description: 'Zoom in' },
      { keys: ['−'], description: 'Zoom out' },
      { keys: ['0'], description: 'Reset to 100%' },
      { keys: ['Space', '+', 'drag'], description: 'Pan' },
    ],
  },
  {
    title: 'Edit history',
    shortcuts: [
      { keys: ['⌘', '+', 'Z'], description: 'Undo' },
      { keys: ['⌘', '+', '⇧', '+', 'Z'], description: 'Redo' },
      { keys: ['⌘', '+', 'Y'], description: 'Redo (Win)' },
    ],
  },
  {
    title: 'Export',
    shortcuts: [
      { keys: ['⌘', '+', 'S'], description: 'Download PNG / ZIP' },
      { keys: ['⌘', '+', '⇧', '+', 'C'], description: 'Copy to clipboard' },
    ],
  },
];

function onKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && open) open = false;
  if (event.key === '?' && !open) open = true;
}

function close(): void {
  open = false;
}
</script>

<svelte:window onkeydown={onKeyDown} />

{#if open}
  <div
    class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
    role="button"
    tabindex="-1"
    aria-label="Close shortcuts"
    onclick={close}
    onkeydown={(e) => e.key === 'Enter' && close()}
  ></div>

  <div
    class="fixed left-1/2 top-1/2 z-50 flex w-[520px] max-w-[90vw] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border border-border bg-card shadow-xl"
    role="dialog"
    aria-modal="true"
    aria-label="Keyboard shortcuts"
  >
    <header class="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4">
      <span class="flex-1 text-[13.5px] font-medium tracking-tight">Keyboard shortcuts</span>
      <button
        type="button"
        class="rounded-md p-1 text-muted-foreground hover:bg-surface2 hover:text-foreground"
        onclick={close}
        aria-label="Close"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </header>

    <div class="grid grid-cols-2 gap-x-6 gap-y-4 overflow-y-auto p-4 max-h-[70vh]">
      {#each groups as group (group.title)}
        <section class="flex flex-col gap-1.5">
          <h3 class="text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3">
            {group.title}
          </h3>
          <ul class="flex flex-col gap-1">
            {#each group.shortcuts as shortcut, i (i)}
              <li class="flex items-center gap-2 text-[12px] text-muted-foreground">
                <span class="flex-1 truncate">{shortcut.description}</span>
                <span class="flex shrink-0 items-center gap-0.5">
                  {#each shortcut.keys as key, j (j)}
                    {#if key === '+' || key === '/'}
                      <span class="text-text3">{key}</span>
                    {:else}
                      <kbd class="rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px] text-foreground">
                        {key}
                      </kbd>
                    {/if}
                  {/each}
                </span>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>

    <footer class="border-t border-border px-4 py-2 font-mono text-[10.5px] text-text3">
      Press <kbd class="mx-0.5 rounded-sm border border-border bg-background px-1 py-px text-foreground">?</kbd>
      anywhere to open this · <kbd class="mx-0.5 rounded-sm border border-border bg-background px-1 py-px text-foreground">Esc</kbd> to close
    </footer>
  </div>
{/if}
