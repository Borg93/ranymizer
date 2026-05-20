<script lang="ts">
import { editor } from '$lib/state.svelte';
import { Spinner } from '$lib/components/ui/spinner';
</script>

<div
  class="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-3 bg-background/85 backdrop-blur-md"
>
  <Spinner class="h-5 w-5 text-primary" />
  <p class="font-mono text-[11px] tracking-wide text-muted-foreground">
    {editor.loadingMessage || 'ocr → privacy filter → map to pixels'}
  </p>
</div>
