<script lang="ts">
import { ChevronDown } from 'lucide-svelte';
import { Badge } from '$lib/components/ui/badge';
import type { Snippet } from 'svelte';

type Props = {
  title: string;
  /** Number badge rendered on the right of the header. Hidden when undefined. */
  count?: number;
  /** Two-way bindable. Defaults to true. */
  expanded?: boolean;
  /** Sticky border style matching the other sidebar sections. */
  bordered?: boolean;
  children: Snippet;
};

let {
  title,
  count,
  expanded = $bindable(true),
  bordered = true,
  children,
}: Props = $props();

const headerId = $props.id();
const bodyId = `${headerId}-body`;
</script>

<section class="px-4 py-3.5 {bordered ? 'border-b border-border' : ''}">
  <button
    type="button"
    id={headerId}
    class="mb-2 flex w-full items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-text3 transition-colors hover:text-foreground"
    aria-expanded={expanded}
    aria-controls={bodyId}
    onclick={() => (expanded = !expanded)}
  >
    <ChevronDown
      class="h-3 w-3 transition-transform duration-150 {expanded ? 'rotate-0' : '-rotate-90'}"
    />
    <span class="flex-1 text-left">{title}</span>
    {#if count !== undefined}
      <Badge variant="secondary" class="font-mono text-[10px] normal-case tracking-normal">
        {count}
      </Badge>
    {/if}
  </button>

  {#if expanded}
    <div id={bodyId}>
      {@render children()}
    </div>
  {/if}
</section>
