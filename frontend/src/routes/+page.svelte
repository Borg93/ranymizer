<script lang="ts">
import { Toaster } from 'svelte-sonner';
import Landing from '$lib/components/Landing.svelte';
import Editor from '$lib/components/Editor.svelte';
import Loading from '$lib/components/Loading.svelte';
import { editor } from '$lib/state.svelte';

function handlePaste(e: ClipboardEvent) {
  if (editor.view !== 'landing') return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const it of items) {
    if (it.type?.startsWith('image/')) {
      const f = it.getAsFile();
      if (f) {
        editor.upload(f);
        e.preventDefault();
        return;
      }
    }
  }
}
</script>

<svelte:window onpaste={handlePaste} />

{#if editor.view === 'landing'}
  <Landing />
{:else}
  <Editor />
{/if}

{#if editor.loading}
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
