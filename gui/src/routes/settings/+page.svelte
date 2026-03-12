<script lang="ts">
	import { onMount } from 'svelte';
	import { getSettings, refreshSettings, saveSettings } from '$lib/stores/settings.svelte';

	const settings = getSettings();

	let defaultContentType = $state('podcast');
	let chunkDuration = $state(300);
	let defaultArtist = $state('');
	let keepFull = $state(false);
	let saving = $state(false);
	let saved = $state(false);

	onMount(async () => {
		await refreshSettings();
		defaultContentType = settings.data.default_content_type ?? 'podcast';
		chunkDuration = settings.data.chunk_duration_seconds ?? 300;
		defaultArtist = settings.data.default_artist ?? '';
		keepFull = settings.data.keep_full ?? false;
	});

	async function handleSave() {
		saving = true;
		saved = false;
		await saveSettings({
			default_content_type: defaultContentType,
			chunk_duration_seconds: chunkDuration,
			default_artist: defaultArtist || undefined,
			keep_full: keepFull,
		});
		saving = false;
		saved = true;
		setTimeout(() => { saved = false; }, 2000);
	}
</script>

<header class="toolbar">
	<a href="/" class="back-link">Back</a>
	<h1>Settings</h1>
	<div></div>
</header>

<main class="settings">
	<div class="field">
		<label for="default-content-type">Default content type</label>
		<select id="default-content-type" bind:value={defaultContentType}>
			<option value="podcast">Podcast</option>
			<option value="music">Music</option>
			<option value="audiobook">Audiobook</option>
		</select>
	</div>

	<div class="field">
		<label for="chunk-duration">Chunk duration (seconds)</label>
		<input id="chunk-duration" type="number" bind:value={chunkDuration} min="30" step="30" />
		<p class="hint">Audio is split into chunks of this length. Default: 300 (5 minutes).</p>
	</div>

	<div class="field">
		<label for="default-artist">Default artist name</label>
		<input id="default-artist" type="text" bind:value={defaultArtist} placeholder="Leave blank to use uploader" />
	</div>

	<div class="field">
		<label>
			<input type="checkbox" bind:checked={keepFull} />
			Keep full audio file after splitting
		</label>
	</div>

	<div class="actions">
		<button onclick={handleSave} disabled={saving}>
			{saving ? 'Saving...' : 'Save'}
		</button>
		{#if saved}
			<span class="saved-msg">Saved</span>
		{/if}
	</div>
</main>

<style>
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid #ddd;
		background: #fff;
	}
	h1 {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}
	.back-link {
		font-size: 0.8rem;
		color: #1976d2;
		text-decoration: none;
	}
	.back-link:hover {
		text-decoration: underline;
	}
	.settings {
		max-width: 500px;
		margin: 1.5rem auto;
		padding: 0 1rem;
	}
	.field {
		margin-bottom: 1.2rem;
	}
	label {
		display: block;
		font-size: 0.85rem;
		font-weight: 500;
		margin-bottom: 0.3rem;
	}
	input[type='number'],
	input[type='text'] {
		width: 100%;
		padding: 0.4rem;
		font-size: 0.85rem;
		border: 1px solid #ddd;
		border-radius: 4px;
	}
	select {
		width: 100%;
		padding: 0.4rem;
		font-size: 0.85rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: #fff;
	}
	input[type='checkbox'] {
		margin-right: 0.4rem;
	}
	.hint {
		font-size: 0.75rem;
		color: #888;
		margin: 0.2rem 0 0;
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	button {
		font-size: 0.85rem;
		padding: 0.4rem 1.2rem;
		border: 1px solid #1976d2;
		border-radius: 4px;
		background: #1976d2;
		color: #fff;
		cursor: pointer;
	}
	button:hover:not(:disabled) {
		background: #1565c0;
	}
	button:disabled {
		opacity: 0.5;
	}
	.saved-msg {
		font-size: 0.8rem;
		color: #43a047;
	}
</style>
