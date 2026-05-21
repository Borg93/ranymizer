<script lang="ts">
import * as Dialog from '$lib/components/ui/dialog';

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
  // Esc is handled by the Dialog itself; we only intercept "?" to open.
  if (event.key === '?' && !open) {
    const t = event.target as HTMLElement | null;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    open = true;
  }
}
</script>

<svelte:window onkeydown={onKeyDown} />

<Dialog.Root bind:open>
  <Dialog.Content class="w-[560px] max-w-[90vw]">
    <Dialog.Header>
      <Dialog.Title>Keyboard shortcuts</Dialog.Title>
      <Dialog.Description>
        Press <kbd class="mx-0.5 rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px] text-foreground">?</kbd> anywhere to open · <kbd class="mx-0.5 rounded-sm border border-border bg-background px-1 py-px font-mono text-[10px] text-foreground">Esc</kbd> to close
      </Dialog.Description>
    </Dialog.Header>

    <div class="grid max-h-[60vh] grid-cols-2 gap-x-6 gap-y-4 overflow-y-auto">
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
  </Dialog.Content>
</Dialog.Root>
