<script lang="ts">
import { Loader2 } from 'lucide-svelte';
import { editor } from '$lib/state.svelte';
</script>

<div
  class="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-3 bg-background/85 backdrop-blur-md"
>
  <Loader2 class="h-5 w-5 animate-spin text-primary" />
  <p class="font-mono text-[11px] tracking-wide text-muted-foreground">
    {editor.loadingMessage || 'ocr → privacy filter → map to pixels'}
  </p>
</div>
