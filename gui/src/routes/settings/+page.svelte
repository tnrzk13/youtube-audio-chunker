<script lang="ts">
	import { onMount } from 'svelte';
	import { getSettings, refreshSettings, saveSettings } from '$lib/stores/settings.svelte';
	import { getTheme, toggleTheme } from '$lib/stores/theme.svelte';

	const settings = getSettings();
	const theme = getTheme();

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
	<button class="theme-toggle" onclick={toggleTheme}>
		{theme.isDark ? '\u2600' : '\u263E'}
	</button>
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
		border-bottom: 1px solid var(--color-border);
		background: var(--color-bg-panel);
	}
	h1 {
		font-size: var(--font-size-lg);
		font-weight: 600;
		margin: 0;
	}
	.back-link {
		font-size: var(--font-size-md);
		color: var(--color-primary);
		text-decoration: none;
		transition: color 0.15s;
	}
	.back-link:hover {
		text-decoration: underline;
	}
	.theme-toggle {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-sm);
		cursor: pointer;
		font-size: var(--font-size-lg);
		padding: 0.15rem 0.4rem;
		line-height: 1;
		transition: all 0.15s;
		color: inherit;
	}
	.theme-toggle:hover {
		background: var(--color-bg-hover);
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
		font-size: var(--font-size-base);
		font-weight: 500;
		margin-bottom: 0.3rem;
	}
	input[type='number'],
	input[type='text'] {
		width: 100%;
		padding: 0.4rem;
		font-size: var(--font-size-base);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		transition: border-color 0.15s;
	}
	input[type='number']:focus,
	input[type='text']:focus {
		outline: none;
		border-color: var(--color-primary);
	}
	select {
		width: 100%;
		padding: 0.4rem;
		font-size: var(--font-size-base);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-panel);
		transition: border-color 0.15s;
	}
	select:focus {
		outline: none;
		border-color: var(--color-primary);
	}
	input[type='checkbox'] {
		margin-right: 0.4rem;
	}
	.hint {
		font-size: var(--font-size-sm);
		color: var(--color-text-hint);
		margin: 0.2rem 0 0;
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	button {
		font-size: var(--font-size-base);
		padding: 0.4rem 1.2rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-md);
		background: var(--color-primary);
		color: #fff;
		cursor: pointer;
		transition: all 0.15s;
	}
	button:hover:not(:disabled) {
		background: var(--color-primary-hover);
	}
	button:disabled {
		opacity: 0.5;
	}
	.saved-msg {
		font-size: var(--font-size-md);
		color: var(--color-success);
	}
</style>
