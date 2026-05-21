<script lang="ts">
/**
 * One per-label PII rule card: description prompt, threshold override,
 * regex post-filter (+ preview), Luhn checksum toggle, reset button.
 *
 * Extracted from SettingsDrawer so the parent's loop stays readable
 * (was ~150 inline lines of identical-looking template per label).
 */
import { RotateCw } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
import {
  DEFAULT_LABEL_DESCRIPTIONS,
  DEFAULT_LABEL_RULES,
  EMPTY_LABEL_RULE,
  type RegexMode,
} from '$lib/types';

type Props = {
  label: string;
  /** Realistic example used by the regex preview chip. */
  sample?: string;
};
let { label, sample = '' }: Props = $props();

/** Per-label canned regex examples — clicking one fills the regex field.
 *  Picked to match the SAMPLES dict in SettingsDrawer so the preview chip
 *  immediately shows ✓ would pass. */
const REGEX_EXAMPLES: Record<string, Array<{ mode: 'full' | 'partial' | 'exclude'; pattern: string; note: string }>> = {
  personnummer: [
    { mode: 'full', pattern: '^\\d{6}[-+]?\\d{4}$', note: '10-digit YYMMDD-NNNN' },
    { mode: 'full', pattern: '^\\d{8}[-+]?\\d{4}$', note: '12-digit YYYYMMDD-NNNN' },
  ],
  organisationsnummer: [
    { mode: 'full', pattern: '^\\d{6}-\\d{4}$', note: 'NNNNNN-NNNN' },
  ],
  phone_number: [
    { mode: 'partial', pattern: '(?:\\+46|0)\\s?7[02369]\\s?\\d{3}\\s?\\d{2}\\s?\\d{2}', note: 'Swedish mobile' },
  ],
  email: [
    { mode: 'full', pattern: '^[^@\\s]+@[^@\\s]+\\.[^@\\s]{2,}$', note: 'standard email shape' },
  ],
  card_number: [
    { mode: 'full', pattern: '^\\d{4}([ -]?\\d{4}){3}$', note: '16-digit groups of 4' },
  ],
  iban: [
    { mode: 'full', pattern: '^[A-Z]{2}\\d{2}[A-Z0-9]{10,30}$', note: 'IBAN shape' },
  ],
  date_of_birth: [
    { mode: 'full', pattern: '^\\d{4}-\\d{2}-\\d{2}$', note: 'ISO YYYY-MM-DD' },
  ],
  ip_address: [
    { mode: 'full', pattern: '^(?:\\d{1,3}\\.){3}\\d{1,3}$', note: 'IPv4' },
  ],
  url: [
    { mode: 'partial', pattern: 'https?://[^\\s]+', note: 'starts with http(s)' },
  ],
  username: [
    { mode: 'exclude', pattern: '^(admin|root|test|user)$', note: 'drop common placeholders' },
  ],
};
const examples = $derived(REGEX_EXAMPLES[label] ?? []);

const rule = $derived(editor.pipelineConfig.gliner.rules[label] ?? { ...EMPTY_LABEL_RULE });
const description = $derived(
  editor.pipelineConfig.gliner.descriptions[label] ??
    DEFAULT_LABEL_DESCRIPTIONS[label] ??
    '',
);
const globalThreshold = $derived(editor.pipelineConfig.gliner.threshold);
const effThreshold = $derived(rule.threshold > 0 ? rule.threshold : globalThreshold);

type Probe = 'ok' | 'reject' | 'invalid' | 'empty';
const probe = $derived.by<Probe>(() => {
  if (!rule.regex.trim()) return 'empty';
  try {
    const re = new RegExp(rule.regex);
    const passes =
      rule.regexMode === 'full'
        ? re.test(sample) && (re.exec(sample)?.[0]?.length ?? 0) === sample.length
        : rule.regexMode === 'partial'
          ? re.test(sample)
          : !re.test(sample);
    return passes ? 'ok' : 'reject';
  } catch {
    return 'invalid';
  }
});

function persist(): void {
  editor.persistPipelineConfig();
}

function setDescription(value: string): void {
  editor.pipelineConfig.gliner.descriptions = {
    ...editor.pipelineConfig.gliner.descriptions,
    [label]: value,
  };
  persist();
}

function patchRule(patch: Partial<typeof EMPTY_LABEL_RULE>): void {
  editor.pipelineConfig.gliner.rules = {
    ...editor.pipelineConfig.gliner.rules,
    [label]: { ...rule, ...patch },
  };
  persist();
}

function resetAll(): void {
  setDescription(DEFAULT_LABEL_DESCRIPTIONS[label] ?? '');
  patchRule(DEFAULT_LABEL_RULES[label] ?? EMPTY_LABEL_RULE);
}
</script>

<div class="flex flex-col gap-2 rounded-md border border-border bg-background/40 p-3">
  <!-- Header -->
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
      onclick={resetAll}
      title="Reset description + regex + threshold + Luhn to defaults"
    >
      <RotateCw class="h-3 w-3" />
      reset
    </button>
  </div>

  <!-- 1. Description -->
  <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
    <span class="flex items-baseline gap-1.5">
      <span class="font-mono text-text3">1</span>
      <span class="text-foreground">Description</span>
      <span class="text-text3">— the prompt the model conditions on</span>
    </span>
    <textarea
      rows="2"
      class="min-w-0 resize-y rounded-sm border border-border bg-background px-2 py-1 text-[12px] leading-snug text-foreground outline-none focus:border-primary"
      value={description}
      oninput={(e) => setDescription((e.currentTarget as HTMLTextAreaElement).value)}
    ></textarea>
    <span class="text-[10.5px] text-text3">
      English sentence GLiNER2 uses to bias its NER head. Be concrete — "Swedish
      personal identity number, 10 digits + dash" finds more than just "id".
    </span>
  </label>

  <!-- 2. Per-label threshold -->
  <label class="flex flex-col gap-1 text-[11px] text-muted-foreground">
    <div class="flex items-center justify-between">
      <span class="flex items-baseline gap-1.5">
        <span class="font-mono text-text3">2</span>
        <span class="text-foreground">Min confidence</span>
        <span class="text-text3">— override the global threshold</span>
      </span>
      <span class="font-mono tabular-nums text-foreground">
        {rule.threshold === 0 ? `${effThreshold.toFixed(2)} (global)` : rule.threshold.toFixed(2)}
      </span>
    </div>
    <input
      type="range"
      min="0"
      max="0.95"
      step="0.05"
      value={rule.threshold}
      oninput={(e) =>
        patchRule({ threshold: Number((e.currentTarget as HTMLInputElement).value) })}
      class="accent-primary"
    />
    <span class="text-[10.5px] text-text3">
      Drop spans the model is unsure about. <span class="font-mono">0</span> uses
      the global value; raise this for noisy categories (e.g. <span class="font-mono">person</span>
      easily false-positives on uppercased nouns).
    </span>
  </label>

  <!-- 3. Regex post-filter -->
  <div class="flex flex-col gap-1 text-[11px] text-muted-foreground">
    <span class="flex items-baseline gap-1.5">
      <span class="font-mono text-text3">3</span>
      <span class="text-foreground">Regex post-filter</span>
      <span class="text-text3">— final sanity check on the matched text</span>
    </span>
    <div class="flex items-center gap-1.5">
      <input
        type="text"
        class="min-w-0 flex-1 rounded-sm border border-border bg-background px-2 py-1 font-mono text-[11px] text-foreground outline-none focus:border-primary"
        placeholder="(leave empty for no filter)"
        value={rule.regex}
        oninput={(e) => patchRule({ regex: (e.currentTarget as HTMLInputElement).value })}
      />
      <select
        class="rounded-sm border border-border bg-background px-1 py-1 text-[11px] text-foreground"
        value={rule.regexMode}
        onchange={(e) =>
          patchRule({ regexMode: (e.currentTarget as HTMLSelectElement).value as RegexMode })}
        title="full = match whole span · partial = match anywhere · exclude = reject on match"
      >
        <option value="full">full</option>
        <option value="partial">partial</option>
        <option value="exclude">exclude</option>
      </select>
    </div>
    <span class="text-[10.5px] text-text3">
      Leave empty to skip. <span class="font-mono">full</span> keeps only spans where
      the entire match equals the regex; <span class="font-mono">partial</span> keeps any span
      containing a match; <span class="font-mono">exclude</span> drops spans the regex matches.
    </span>

    {#if examples.length}
      <div class="mt-1 flex flex-wrap items-center gap-1 text-[10px]">
        <span class="text-text3">Try:</span>
        {#each examples as ex (ex.pattern)}
          <button
            type="button"
            class="rounded-sm border border-border bg-background px-1.5 py-0.5 font-mono text-foreground transition-colors hover:border-primary hover:bg-surface2"
            onclick={() => patchRule({ regex: ex.pattern, regexMode: ex.mode })}
            title={`${ex.mode}: ${ex.note}`}
          >
            {ex.pattern.length > 28 ? ex.pattern.slice(0, 26) + '…' : ex.pattern}
          </button>
        {/each}
      </div>
    {/if}
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

  <!-- 4. Luhn checksum -->
  <label class="flex items-start gap-2 rounded-sm border border-border bg-transparent px-2 py-1.5 text-[11.5px] text-foreground hover:bg-surface2">
    <input
      type="checkbox"
      class="mt-0.5 accent-primary"
      checked={rule.validateLuhn}
      onchange={() => patchRule({ validateLuhn: !rule.validateLuhn })}
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
