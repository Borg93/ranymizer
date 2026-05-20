<script lang="ts">
import { X, RotateCcw, Play } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import { DEFAULT_PII_LABELS } from '$lib/types';
import { Button } from '$lib/components/ui/button';
import CollapsibleSection from './CollapsibleSection.svelte';

function close(): void {
  editor.settingsOpen = false;
}

function toggleLabel(label: string): void {
  const set = new Set(editor.pipelineConfig.gliner.enabledLabels);
  if (set.has(label)) set.delete(label);
  else set.add(label);
  editor.pipelineConfig.gliner.enabledLabels = [...set];
  editor.persistPipelineConfig();
}

function setThreshold(value: number): void {
  editor.pipelineConfig.gliner.threshold = value;
  editor.persistPipelineConfig();
}

function toggleOcrFlag(key: keyof typeof editor.pipelineConfig.ocr): void {
  editor.pipelineConfig.ocr[key] = !editor.pipelineConfig.ocr[key];
  editor.persistPipelineConfig();
}

function applyAndRun(): Promise<void> {
  close();
  return editor.run();
}

function resetDefaults(): void {
  editor.resetPipelineConfig();
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && editor.settingsOpen) close();
}

const enabledSet = $derived(new Set(editor.pipelineConfig.gliner.enabledLabels));
const labelCount = $derived(editor.pipelineConfig.gliner.enabledLabels.length);
</script>

<svelte:window onkeydown={onKeyDown} />

{#if editor.settingsOpen}
  <div
    class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
    role="button"
    tabindex="-1"
    aria-label="Close settings"
    onclick={close}
    onkeydown={(e) => e.key === 'Enter' && close()}
  ></div>

  <div
    class="fixed right-0 top-0 z-50 flex h-screen w-[360px] max-w-[88vw] flex-col border-l border-border bg-card shadow-xl"
    role="dialog"
    aria-modal="true"
    aria-label="Pipeline settings"
  >
    <header class="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4">
      <span class="flex-1 text-[13.5px] font-medium tracking-tight">Pipeline settings</span>
      <Button
        variant="ghost"
        size="sm"
        class="h-7 w-7 p-0"
        onclick={close}
        aria-label="Close settings"
      >
        <X class="h-3.5 w-3.5" />
      </Button>
    </header>

    <div class="flex-1 overflow-y-auto">
      <CollapsibleSection title="GLiNER detection">
        <div class="flex flex-col gap-3">
          <label class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between text-[11.5px] text-muted-foreground">
              <span>Confidence threshold</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.gliner.threshold.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={editor.pipelineConfig.gliner.threshold}
              oninput={(e) => setThreshold(Number((e.currentTarget as HTMLInputElement).value))}
              class="accent-primary"
            />
            <span class="font-mono text-[10.5px] text-text3">
              Lower = more recall, more false positives.
            </span>
          </label>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="PII labels" count={labelCount}>
        <div class="grid grid-cols-2 gap-1">
          {#each DEFAULT_PII_LABELS as label (label)}
            {@const isOn = enabledSet.has(label)}
            <button
              type="button"
              class="flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-left text-[12.5px] text-foreground transition-colors hover:bg-surface2 data-[active=true]:border-border data-[active=true]:bg-surface2 data-[active=false]:opacity-50"
              data-active={isOn}
              onclick={() => toggleLabel(label)}
            >
              <span
                class="h-3.5 w-[3px] shrink-0 rounded-[1.5px]"
                style:background={editor.catMeta[label]?.color ?? '#888'}
              ></span>
              <span class="flex-1 truncate">
                {editor.catMeta[label]?.label ?? label}
              </span>
            </button>
          {/each}
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="OCR preprocessing" expanded={false} bordered={false}>
        <div class="flex flex-col gap-2 text-[12.5px]">
          <label class="flex items-center gap-2 rounded-md border border-border bg-transparent px-2 py-1.5 hover:bg-surface2">
            <input
              type="checkbox"
              class="accent-primary"
              checked={editor.pipelineConfig.ocr.useDocOrientationClassify}
              onchange={() => toggleOcrFlag('useDocOrientationClassify')}
            />
            <span class="flex-1">Document orientation classify</span>
          </label>
          <label class="flex items-center gap-2 rounded-md border border-border bg-transparent px-2 py-1.5 hover:bg-surface2">
            <input
              type="checkbox"
              class="accent-primary"
              checked={editor.pipelineConfig.ocr.useDocUnwarping}
              onchange={() => toggleOcrFlag('useDocUnwarping')}
            />
            <span class="flex-1">Document unwarping</span>
          </label>
          <label class="flex items-center gap-2 rounded-md border border-border bg-transparent px-2 py-1.5 hover:bg-surface2">
            <input
              type="checkbox"
              class="accent-primary"
              checked={editor.pipelineConfig.ocr.useTextlineOrientation}
              onchange={() => toggleOcrFlag('useTextlineOrientation')}
            />
            <span class="flex-1">Text-line orientation</span>
          </label>
          <p class="font-mono text-[10.5px] text-text3">
            Server-side preprocessing flags. Applied on the next Run.
          </p>
        </div>
      </CollapsibleSection>
    </div>

    <footer class="flex shrink-0 items-center gap-2 border-t border-border px-4 py-3">
      <Button variant="ghost" size="sm" class="h-8 gap-1.5" onclick={resetDefaults}>
        <RotateCcw class="h-3.5 w-3.5" />
        <span class="text-[12px]">Reset</span>
      </Button>
      <span class="flex-1"></span>
      <Button
        variant="default"
        size="sm"
        class="h-8 gap-1.5"
        disabled={!editor.hasImage || editor.loading}
        onclick={applyAndRun}
      >
        <Play class="h-3.5 w-3.5" />
        <span class="text-[12px]">Apply & Run</span>
      </Button>
    </footer>
  </div>
{/if}
