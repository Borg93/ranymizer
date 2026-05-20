/**
 * Updater store and helpers for @tauri-apps/plugin-updater.
 *
 * Usage:
 *   import { onMount } from 'svelte';
 *   import { ensureUpdateChecked, installAvailableUpdate, updaterState } from '$lib/updater';
 *
 *   onMount(() => { ensureUpdateChecked().catch(console.error); });
 *
 *   {#if $updaterState.hasUpdate}
 *     <button onclick={() => installAvailableUpdate()}>
 *       Install v{$updaterState.latestVersion}
 *     </button>
 *   {/if}
 */

import { get, writable } from 'svelte/store';
import { check, type DownloadEvent, type Update } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';

export type UpdaterState = {
	checked: boolean;
	checking: boolean;
	installing: boolean;
	hasUpdate: boolean;
	latestVersion: string;
	update: Update | null;
	error: string;
};

const initialState: UpdaterState = {
	checked: false,
	checking: false,
	installing: false,
	hasUpdate: false,
	latestVersion: '',
	update: null,
	error: '',
};

export const updaterState = writable<UpdaterState>({ ...initialState });

/** In-flight check, so concurrent callers share one request. */
let checkPromise: Promise<void> | null = null;

function errorMessage(error: unknown, fallback: string): string {
	if (error instanceof Error && error.message) return error.message;
	if (typeof error === 'string' && error.trim()) return error;
	try {
		const text = JSON.stringify(error);
		return text && text !== '{}' ? text : fallback;
	} catch {
		return fallback;
	}
}

/**
 * Check for an update. By default only runs once per session — pass
 * `force = true` to re-check on demand (e.g. from a Settings button).
 */
export async function ensureUpdateChecked(force = false): Promise<void> {
	if (checkPromise) {
		await checkPromise;
		return;
	}

	const current = get(updaterState);
	if (!force && (current.checked || current.checking)) return;

	const task = (async () => {
		updaterState.update((s) => ({ ...s, checking: true, error: '' }));
		try {
			const update = await check();
			updaterState.update((s) => ({
				...s,
				checked: true,
				checking: false,
				hasUpdate: Boolean(update),
				latestVersion: update?.version ?? '',
				update: update ?? null,
			}));
		} catch (error) {
			updaterState.update((s) => ({
				...s,
				checked: true,
				checking: false,
				error: errorMessage(error, 'Failed to check for update'),
			}));
			throw error;
		}
	})();

	checkPromise = task;
	try {
		await task;
	} finally {
		checkPromise = null;
	}
}

/**
 * Download and install the available update, then relaunch the app.
 * Optionally pass an onProgress callback to surface download events.
 */
export async function installAvailableUpdate(
	onProgress?: (event: DownloadEvent) => void,
): Promise<void> {
	const current = get(updaterState);
	if (current.installing) return;

	if (!current.update) {
		await ensureUpdateChecked(true);
	}

	const refreshed = get(updaterState);
	if (!refreshed.update) return;

	updaterState.update((s) => ({ ...s, installing: true, error: '' }));
	try {
		await refreshed.update.downloadAndInstall((event) => onProgress?.(event));
		await relaunch();
	} catch (error) {
		updaterState.update((s) => ({
			...s,
			installing: false,
			error: errorMessage(error, 'Failed to install update'),
		}));
		throw error;
	}
}

/** Reset the store (mostly useful for tests). */
export function resetUpdaterState(): void {
	updaterState.set({ ...initialState });
}
