<script lang="ts">
	import { onMount } from 'svelte';
	import { addToQueue, processQueue } from '$lib/stores/library.svelte';
	import { getSettings, refreshSettings } from '$lib/stores/settings.svelte';
	import { setActive } from '$lib/stores/progress.svelte';
	import { getGarminStatus } from '$lib/stores/garmin.svelte';
	import type { ContentType } from '$lib/types';

	const settings = getSettings();
	const garmin = getGarminStatus();

	let urlInput = $state('');
	let contentType = $state<ContentType>('podcast');
	let submitting = $state(false);
	let errorMsg = $state('');

	onMount(async () => {
		await refreshSettings();
		contentType = (settings.data.default_content_type as ContentType) ?? 'podcast';
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	}

	async function handleSubmit() {
		const urls = urlInput
			.split('\n')
			.map((u) => u.trim())
			.filter((u) => u.length > 0);

		if (urls.length === 0) return;

		submitting = true;
		errorMsg = '';
		try {
			const result = await addToQueue(urls, contentType);
			if (result.skipped.length > 0 && result.added.length === 0) {
				errorMsg = `Skipped (already exists): ${result.skipped.join(', ')}`;
				return;
			}
			urlInput = '';

			setActive(true);
			await processQueue({ noTransfer: !garmin.data.connected });
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			submitting = false;
			setActive(false);
		}
	}
</script>

<form class="add-form" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
	<textarea
		bind:value={urlInput}
		placeholder="Paste YouTube URL(s)..."
		rows="1"
		disabled={submitting}
		onkeydown={handleKeydown}
	></textarea>
	<div class="form-row">
		<select bind:value={contentType} disabled={submitting}>
			<option value="music">Music</option>
			<option value="podcast">Podcast</option>
			<option value="audiobook">Audiobook</option>
		</select>
		<button type="submit" disabled={submitting || urlInput.trim().length === 0}>
			{submitting ? 'Syncing...' : '+ Add'}
		</button>
	</div>
	{#if errorMsg}
		<div class="error">{errorMsg}</div>
	{/if}
</form>

<style>
	.add-form {
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
	}
	textarea {
		width: 100%;
		font-family: inherit;
		font-size: var(--font-size-md);
		padding: 0.4rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		resize: vertical;
		box-sizing: border-box;
		transition: border-color 0.15s;
	}
	textarea:focus {
		outline: none;
		border-color: var(--color-primary);
	}
	.form-row {
		display: flex;
		gap: 0.4rem;
		margin-top: 0.4rem;
	}
	select {
		font-size: var(--font-size-md);
		padding: 0.3rem 0.4rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-panel);
		transition: border-color 0.15s;
	}
	select:focus {
		outline: none;
		border-color: var(--color-primary);
	}
	button {
		font-size: var(--font-size-md);
		padding: 0.3rem 0.75rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-md);
		background: var(--color-primary);
		color: #fff;
		cursor: pointer;
		white-space: nowrap;
		transition: all 0.15s;
	}
	button:hover:not(:disabled) {
		background: var(--color-primary-hover);
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		margin-top: 0.3rem;
	}
</style>
