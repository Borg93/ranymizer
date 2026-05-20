<script lang="ts">
import { Toaster } from 'svelte-sonner';
import Editor from '$lib/components/Editor.svelte';
import Loading from '$lib/components/Loading.svelte';
import { editor } from '$lib/state.svelte';

function handlePaste(event: ClipboardEvent): void {
  if (editor.hasImage) return; // editing in-flight; let the focused element handle paste
  const items = event.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (!item.type?.startsWith('image/')) continue;
    const file = item.getAsFile();
    if (!file) continue;
    editor.upload(file);
    event.preventDefault();
    return;
  }
}
</script>

<svelte:window onpaste={handlePaste} />

<Editor />

<!-- Full-screen blur only during the initial load (no image yet). During a
     re-run we show a localised spinner inside the canvas so the sidebars
     and navbar stay interactive. -->
{#if editor.loading && !editor.hasImage}
  <Loading />
{/if}

<Toaster
  position="bottom-center"
  theme="system"
  toastOptions={{
    classes: {
      toast:
        'bg-card border border-border text-foreground font-mono text-xs rounded-md shadow-sm'
    }
  }}
/>
