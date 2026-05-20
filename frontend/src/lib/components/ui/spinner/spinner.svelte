<script lang="ts">
import { Loader2 } from 'lucide-svelte';
import { cn } from '$lib/utils';

type Props = { class?: string; size?: number; strokeWidth?: number };
let { class: className, size, strokeWidth }: Props = $props();
</script>

<Loader2
  role="status"
  aria-label="Loading"
  class={cn('size-4 animate-spin', className)}
  {size}
  {strokeWidth}
/>
