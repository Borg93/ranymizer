<script lang="ts">
/**
 * Fullscreen settings view. NOT a modal/drawer — takes over the entire
 * viewport so the pipeline graph and node forms have real room to breathe.
 *
 * All knobs live on the nodes inside <PipelineSketch>. This wrapper only
 * provides the header, the fullscreen container, and the Apply/Reset footer.
 */
import { Play, RotateCcw, X } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import { Button } from '$lib/components/ui/button';
import PipelineSketch from './PipelineSketch.svelte';

function close(): void {
  editor.settingsOpen = false;
}

function applyAndRun(): Promise<void> {
  // Stay in the settings view — the user explicitly asked for this so they
  // can A/B knob changes against the result without bouncing back to the
  // canvas every time. The X / Esc still close.
  return editor.run();
}

function resetDefaults(): void {
  editor.resetPipelineConfig();
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && editor.settingsOpen) close();
}
</script>

<svelte:window onkeydown={onKeyDown} />

{#if editor.settingsOpen}
  <div
    class="fixed inset-0 z-50 flex flex-col bg-background"
    role="dialog"
    aria-modal="true"
    aria-label="Pipeline settings"
  >
    <!-- Header -->
    <header class="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-card px-5">
      <span class="text-[14px] font-semibold tracking-tight">Pipeline settings</span>
      <span class="text-[11.5px] text-muted-foreground">
        Click a node to expand its settings inline. Drag nodes, pan with empty space, scroll to zoom.
      </span>
      <span class="flex-1"></span>
      <Button variant="ghost" size="sm" onclick={resetDefaults}>
        <RotateCcw class="mr-1 h-3.5 w-3.5" />
        Reset to defaults
      </Button>
      <Button
        variant="default"
        size="sm"
        disabled={!editor.hasImage || editor.loading}
        onclick={applyAndRun}
      >
        <Play class="mr-1 h-3.5 w-3.5" />
        Apply &amp; Run
      </Button>
      <Button
        variant="ghost"
        size="sm"
        class="h-8 w-8 p-0"
        onclick={close}
        aria-label="Close settings"
        title="Close (Esc)"
      >
        <X class="h-4 w-4" />
      </Button>
    </header>

    <!-- Pipeline graph fills the remaining viewport. -->
    <div class="min-h-0 flex-1">
      <PipelineSketch />
    </div>
  </div>
{/if}
