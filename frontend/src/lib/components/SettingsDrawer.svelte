<script lang="ts">
import { Play, RotateCcw, RotateCw, X } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import {
  DEFAULT_LABEL_DESCRIPTIONS,
  DEFAULT_LABEL_RULES,
  DEFAULT_PII_LABELS,
  EMPTY_LABEL_RULE,
  type RegexMode,
} from '$lib/types';
import { Button } from '$lib/components/ui/button';
import CollapsibleSection from './CollapsibleSection.svelte';
import PipelineSketch from './PipelineSketch.svelte';

function close(): void {
  editor.settingsOpen = false;
}

function persist(): void {
  editor.persistPipelineConfig();
}

function toggleLabel(label: string): void {
  const enabled = new Set(editor.pipelineConfig.gliner.enabledLabels);
  if (enabled.has(label)) enabled.delete(label);
  else enabled.add(label);
  editor.pipelineConfig.gliner.enabledLabels = [...enabled];
  persist();
}

function descriptionFor(label: string): string {
  return (
    editor.pipelineConfig.gliner.descriptions[label] ??
    DEFAULT_LABEL_DESCRIPTIONS[label] ??
    ''
  );
}

function setDescription(label: string, value: string): void {
  editor.pipelineConfig.gliner.descriptions = {
    ...editor.pipelineConfig.gliner.descriptions,
    [label]: value,
  };
  persist();
}

function resetDescription(label: string): void {
  setDescription(label, DEFAULT_LABEL_DESCRIPTIONS[label] ?? '');
}

function ruleFor(label: string) {
  return editor.pipelineConfig.gliner.rules[label] ?? { ...EMPTY_LABEL_RULE };
}

function patchRule(label: string, patch: Partial<typeof EMPTY_LABEL_RULE>): void {
  editor.pipelineConfig.gliner.rules = {
    ...editor.pipelineConfig.gliner.rules,
    [label]: { ...ruleFor(label), ...patch },
  };
  persist();
}

function resetRule(label: string): void {
  patchRule(label, DEFAULT_LABEL_RULES[label] ?? EMPTY_LABEL_RULE);
}

/**
 * Quick "does this string match?" preview shown next to the regex field.
 * Returns:
 *   'ok'      regex parses and would let example text through
 *   'reject'  regex parses but the example would be filtered out
 *   'invalid' regex itself is not parseable
 *   'empty'   no regex set
 */
function regexProbe(rule: ReturnType<typeof ruleFor>, sample: string): 'ok' | 'reject' | 'invalid' | 'empty' {
  if (!rule.regex.trim()) return 'empty';
  try {
    const re = new RegExp(rule.regex);
    const matches =
      rule.regexMode === 'full' ? re.test(sample) && (re.exec(sample)?.[0]?.length ?? 0) === sample.length
      : rule.regexMode === 'partial' ? re.test(sample)
      : !re.test(sample); // exclude
    return matches ? 'ok' : 'reject';
  } catch {
    return 'invalid';
  }
}

/** Tiny realistic Swedish sample per label, used by the preview chip. */
const SAMPLES: Record<string, string> = {
  person: 'Sven Andersson',
  email: 'sven.andersson@exempel.se',
  phone_number: '+46 70-123 45 67',
  address: 'Sveavägen 12, 113 57 Stockholm',
  date_of_birth: '1985-03-15',
  personnummer: '850315-2389',
  organisationsnummer: '556677-1234',
  bank_account: '5050-1055',
  iban: 'SE3550000000054910000003',
  card_number: '4111 1111 1111 1111',
  url: 'https://ranymizer.dev',
  ip_address: '192.168.1.1',
  username: 'sven_a',
};

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

// Shared classnames for the form controls (kept identical so the drawer feels uniform).
const inputCls =
  'min-w-0 w-full rounded-sm border border-border bg-background px-2 py-1 text-[12px] text-foreground outline-none focus:border-primary';
const fieldLabelCls =
  'flex flex-col gap-1 text-[11px] text-muted-foreground';
const rowToggleCls =
  'flex items-center gap-2 rounded-md border border-border bg-transparent px-2 py-1.5 text-[12px] text-foreground hover:bg-surface2';
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
    class="fixed right-0 top-0 z-50 flex h-screen w-[480px] max-w-[94vw] flex-col border-l border-border bg-card shadow-xl"
    role="dialog"
    aria-modal="true"
    aria-label="Pipeline settings"
  >
    <header class="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4">
      <span class="flex-1 text-[13.5px] font-medium tracking-tight">Pipeline settings</span>
      <Button variant="ghost" size="icon-sm" onclick={close} aria-label="Close">
        <X />
      </Button>
    </header>

    <div class="flex-1 overflow-y-auto">
      <!-- ─── How the pipeline works ─────────────────────────────────── -->
      <CollapsibleSection title="How the pipeline works">
        <PipelineSketch />
      </CollapsibleSection>

      <!-- ─── GLiNER2 (PII) ──────────────────────────────────────────── -->
      <CollapsibleSection title="GLiNER2 — PII detection">
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <span>Model</span>
            <input
              type="text"
              class={inputCls}
              value={editor.pipelineConfig.gliner.modelName}
              oninput={(e) => {
                editor.pipelineConfig.gliner.modelName = (e.currentTarget as HTMLInputElement).value;
                persist();
              }}
            />
            <span class="text-[10.5px] text-text3">
              Hugging Face id or local path. Switching this re-loads the model on next Run.
            </span>
          </label>

          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
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
              oninput={(e) => {
                editor.pipelineConfig.gliner.threshold = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
            <span class="text-[10.5px] text-text3">Lower = more recall, more false positives.</span>
          </label>
        </div>
      </CollapsibleSection>

      <!-- ─── PII labels ─────────────────────────────────────────────── -->
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

      <!-- ─── Label rules ────────────────────────────────────────────── -->
      <CollapsibleSection title="Label rules" expanded={false}>
        <div
          class="mb-3 flex flex-col gap-1.5 rounded-md border border-border bg-background/60 p-3 text-[10.5px] leading-relaxed text-muted-foreground"
        >
          <p>
            Each label has up to four knobs. They run in this order on every
            candidate the model proposes:
          </p>
          <ol class="ml-4 list-decimal space-y-0.5">
            <li>
              <span class="text-foreground">Description</span> — the soft prompt
              the model gets ("look for things that match this English sentence").
              Better description = better recall.
            </li>
            <li>
              <span class="text-foreground">Min confidence</span> — drop spans
              the model is unsure about. <span class="font-mono">0</span> = use
              the global threshold above.
            </li>
            <li>
              <span class="text-foreground">Regex</span> — a final sanity check
              on the matched text. <span class="font-mono">full</span> matches the
              whole span, <span class="font-mono">partial</span> matches anywhere,
              <span class="font-mono">exclude</span> rejects the span if it
              matches. Empty = no filter.
            </li>
            <li>
              <span class="text-foreground">Luhn checksum</span> — only useful
              for personnummer and credit cards. Reject digit-only spans whose
              Luhn check fails.
            </li>
          </ol>
          <p class="pt-1">
            None of these can <em>invent</em> hits — they only reject false
            positives the model already produced.
          </p>
        </div>

        <div class="flex flex-col gap-4">
          {#each DEFAULT_PII_LABELS as label (label)}
            {@const rule = ruleFor(label)}
            {@const effThreshold =
              rule.threshold > 0 ? rule.threshold : editor.pipelineConfig.gliner.threshold}
            {@const sample = SAMPLES[label] ?? ''}
            {@const probe = regexProbe(rule, sample)}

            <div class="flex flex-col gap-2 rounded-md border border-border bg-background/40 p-3">
              <!-- Row header -->
              <div class="flex items-center gap-2">
                <span
                  class="h-3.5 w-[3px] shrink-0 rounded-[1.5px]"
                  style:background={editor.catMeta[label]?.color ?? '#888'}
                ></span>
                <span class="flex-1 text-[12.5px] font-medium text-foreground">
                  {editor.catMeta[label]?.label ?? label}
                </span>
                <button
                  type="button"
                  class="flex items-center gap-1 rounded-sm border border-border px-1.5 py-0.5 text-[10px] text-text3 transition-colors hover:bg-surface2 hover:text-foreground"
                  onclick={() => {
                    resetDescription(label);
                    resetRule(label);
                  }}
                  title="Reset description + regex + threshold + Luhn to defaults"
                >
                  <RotateCw class="h-3 w-3" />
                  reset
                </button>
              </div>

              <!-- 1. Description -->
              <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
                <span>1 — Description (the prompt GLiNER2 sees)</span>
                <textarea
                  rows="2"
                  class="min-w-0 resize-y rounded-sm border border-border bg-background px-2 py-1 text-[12px] leading-snug text-foreground outline-none focus:border-primary"
                  value={descriptionFor(label)}
                  oninput={(e) =>
                    setDescription(label, (e.currentTarget as HTMLTextAreaElement).value)}
                ></textarea>
              </label>

              <!-- 2. Per-label threshold -->
              <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
                <div class="flex items-center justify-between">
                  <span>2 — Min confidence (override)</span>
                  <span class="font-mono tabular-nums text-foreground">
                    {rule.threshold === 0
                      ? `${effThreshold.toFixed(2)} (global)`
                      : rule.threshold.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.95"
                  step="0.05"
                  value={rule.threshold}
                  oninput={(e) =>
                    patchRule(label, {
                      threshold: Number((e.currentTarget as HTMLInputElement).value),
                    })}
                  class="accent-primary"
                />
                <span class="text-[10.5px] text-text3">
                  Slide to <span class="font-mono">0</span> to use the global threshold above.
                </span>
              </label>

              <!-- 3. Regex post-filter -->
              <div class="flex flex-col gap-1 text-[11px] text-muted-foreground">
                <span>3 — Regex post-filter</span>
                <div class="flex items-center gap-1.5">
                  <input
                    type="text"
                    class="min-w-0 flex-1 rounded-sm border border-border bg-background px-2 py-1 font-mono text-[11px] text-foreground outline-none focus:border-primary"
                    placeholder="(leave empty for no filter)"
                    value={rule.regex}
                    oninput={(e) =>
                      patchRule(label, { regex: (e.currentTarget as HTMLInputElement).value })}
                  />
                  <select
                    class="rounded-sm border border-border bg-background px-1 py-1 text-[11px] text-foreground"
                    value={rule.regexMode}
                    onchange={(e) =>
                      patchRule(label, {
                        regexMode: (e.currentTarget as HTMLSelectElement).value as RegexMode,
                      })}
                  >
                    <option value="full">full</option>
                    <option value="partial">partial</option>
                    <option value="exclude">exclude</option>
                  </select>
                </div>
                {#if sample}
                  <div class="mt-0.5 flex items-center gap-2 text-[10.5px]">
                    <span class="text-text3">Preview on</span>
                    <code class="rounded-sm bg-background px-1 py-px font-mono text-foreground">
                      {sample}
                    </code>
                    {#if probe === 'ok'}
                      <span class="text-emerald-400">✓ would pass</span>
                    {:else if probe === 'reject'}
                      <span class="text-amber-500">✗ would be filtered out</span>
                    {:else if probe === 'invalid'}
                      <span class="text-destructive">⚠ regex is invalid</span>
                    {/if}
                  </div>
                {/if}
              </div>

              <!-- 4. Luhn checksum (only shown when relevant by default; toggle present always) -->
              <label class="flex items-start gap-2 rounded-sm border border-border bg-transparent px-2 py-1.5 text-[11.5px] text-foreground hover:bg-surface2">
                <input
                  type="checkbox"
                  class="mt-0.5 accent-primary"
                  checked={rule.validateLuhn}
                  onchange={() => patchRule(label, { validateLuhn: !rule.validateLuhn })}
                />
                <span class="flex-1">
                  4 — Validate Luhn checksum
                  <span class="block font-mono text-[10px] text-text3">
                    Recommended for <span class="text-foreground">personnummer</span> and
                    <span class="text-foreground">card_number</span>; rejects digit-only spans
                    that fail the Luhn check. Ignored when the matched text isn't all digits.
                  </span>
                </span>
              </label>
            </div>
          {/each}
        </div>
      </CollapsibleSection>

      <!-- ─── PaddleOCR-VL layout + preprocessing ────────────────────── -->
      <CollapsibleSection title="PaddleOCR — layout & preprocessing" expanded={false}>
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Layout threshold</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.paddleocr.layoutThreshold.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={editor.pipelineConfig.paddleocr.layoutThreshold}
              oninput={(e) => {
                editor.pipelineConfig.paddleocr.layoutThreshold = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <div class="flex flex-col gap-2 text-[12px]">
            {#each [
              ['useDocOrientationClassify', 'Document orientation classify'],
              ['useDocUnwarping', 'Document unwarping'],
              ['useTextlineOrientation', 'Text-line orientation'],
              ['useChartRecognition', 'Chart recognition'],
              ['useSealRecognition', 'Seal (stamp) recognition'],
              ['useOcrForImageBlock', 'OCR inside image blocks'],
            ] as [key, label] (key)}
              {@const k = key as keyof typeof editor.pipelineConfig.paddleocr}
              <label class={rowToggleCls}>
                <input
                  type="checkbox"
                  class="accent-primary"
                  checked={editor.pipelineConfig.paddleocr[k] as boolean}
                  onchange={() => {
                    editor.pipelineConfig.paddleocr[k] =
                      !editor.pipelineConfig.paddleocr[k] as never;
                    persist();
                  }}
                />
                <span class="flex-1">{label}</span>
              </label>
            {/each}
          </div>
        </div>
      </CollapsibleSection>

      <!-- ─── VLM sampling ───────────────────────────────────────────── -->
      <CollapsibleSection title="VLM sampling" expanded={false}>
        <div class="flex flex-col gap-3">
          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Temperature</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.vlm.temperature.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1.5"
              step="0.05"
              value={editor.pipelineConfig.vlm.temperature}
              oninput={(e) => {
                editor.pipelineConfig.vlm.temperature = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>top_p</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.vlm.topP.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="1"
              step="0.05"
              value={editor.pipelineConfig.vlm.topP}
              oninput={(e) => {
                editor.pipelineConfig.vlm.topP = Number((e.currentTarget as HTMLInputElement).value);
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <label class={fieldLabelCls}>
            <div class="flex items-center justify-between">
              <span>Repetition penalty</span>
              <span class="font-mono tabular-nums text-foreground">
                {editor.pipelineConfig.vlm.repetitionPenalty.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="2"
              step="0.05"
              value={editor.pipelineConfig.vlm.repetitionPenalty}
              oninput={(e) => {
                editor.pipelineConfig.vlm.repetitionPenalty = Number(
                  (e.currentTarget as HTMLInputElement).value,
                );
                persist();
              }}
              class="accent-primary"
            />
          </label>

          <label class={fieldLabelCls}>
            <span>Max new tokens</span>
            <input
              type="number"
              min="32"
              max="32768"
              step="32"
              class={inputCls}
              value={editor.pipelineConfig.vlm.maxNewTokens}
              oninput={(e) => {
                const value = Number((e.currentTarget as HTMLInputElement).value);
                if (Number.isFinite(value)) {
                  editor.pipelineConfig.vlm.maxNewTokens = value;
                  persist();
                }
              }}
            />
          </label>

          <div class="grid grid-cols-2 gap-2">
            <label class={fieldLabelCls}>
              <span>min_pixels</span>
              <input
                type="number"
                min="0"
                step="1000"
                class={inputCls}
                value={editor.pipelineConfig.vlm.minPixels}
                oninput={(e) => {
                  const value = Number((e.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(value)) {
                    editor.pipelineConfig.vlm.minPixels = value;
                    persist();
                  }
                }}
              />
            </label>
            <label class={fieldLabelCls}>
              <span>max_pixels</span>
              <input
                type="number"
                min="0"
                step="1000"
                class={inputCls}
                value={editor.pipelineConfig.vlm.maxPixels}
                oninput={(e) => {
                  const value = Number((e.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(value)) {
                    editor.pipelineConfig.vlm.maxPixels = value;
                    persist();
                  }
                }}
              />
            </label>
          </div>
          <span class="text-[10.5px] text-text3">
            VLM image preprocessing bounds. 0 = leave default.
          </span>
        </div>
      </CollapsibleSection>
    </div>

    <footer class="flex shrink-0 items-center gap-2 border-t border-border px-4 py-3">
      <Button variant="ghost" size="sm" onclick={resetDefaults}>
        <RotateCcw />
        Reset
      </Button>
      <span class="flex-1"></span>
      <Button
        variant="default"
        size="sm"
        disabled={!editor.hasImage || editor.loading}
        onclick={applyAndRun}
      >
        <Play />
        Apply & Run
      </Button>
    </footer>
  </div>
{/if}
