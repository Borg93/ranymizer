<script lang="ts">
	import { invoke } from '@tauri-apps/api/core';
	import { Button } from '$lib/components/ui/button';

	let name = $state('');
	let greeting = $state('');
	let error = $state('');

	async function handleGreet() {
		error = '';
		try {
			greeting = await invoke<string>('greet', { name });
		} catch (e) {
			error = String(e);
		}
	}
</script>

<main class="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
	<div class="text-center">
		<h1 class="text-3xl font-semibold">SvelteKit + Tauri</h1>
		<p class="text-muted-foreground mt-2 text-sm">
			Svelte 5 · Tauri 2 · Tailwind 4 · shadcn-svelte · Bun
		</p>
	</div>

	<div class="flex w-full max-w-sm flex-col gap-3">
		<input
			bind:value={name}
			placeholder="Your name"
			class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring h-9 w-full rounded-md border px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
		/>
		<Button onclick={handleGreet}>Greet</Button>
	</div>

	{#if greeting}
		<p class="text-lg">{greeting}</p>
	{/if}

	{#if error}
		<p class="text-destructive text-sm">{error}</p>
	{/if}
</main>
