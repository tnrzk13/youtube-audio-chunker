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
	<a href="/" class="toolbar-icon">{'\u2190'}</a>
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

	<div class="about">
		<h2>About</h2>
		<p class="about-name">youtube-audio-chunker <span class="about-version">v0.1.0</span></p>
		<p class="about-desc">Download YouTube audio, split into navigable chunks, and sideload to Garmin watches.</p>
		<p class="about-author">
			Built by <a href="https://www.tonykwok.info/" target="_blank" rel="noopener">Tony Kwok</a>
		</p>
		<p class="about-links">
			<a href="https://github.com/tnrzk13" target="_blank" rel="noopener">GitHub</a>
		</p>
	</div>
</main>

<style>
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		box-shadow: var(--shadow-toolbar);
		background: var(--color-bg-panel);
		flex-shrink: 0;
		z-index: 1;
	}
	h1 {
		font-size: var(--font-size-lg);
		font-weight: 600;
		margin: 0;
	}
	.toolbar-icon {
		display: flex;
		align-items: center;
		text-decoration: none;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		cursor: pointer;
		font-size: var(--font-size-lg);
		padding: 0.45rem 0.5rem;
		line-height: 1;
		color: inherit;
		transition: all 0.15s;
	}
	.toolbar-icon:hover {
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
	.actions button {
		font-size: var(--font-size-base);
		padding: 0.4rem 1.2rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-md);
		background: var(--color-primary);
		color: #fff;
		cursor: pointer;
		transition: all 0.15s;
	}
	.actions button:hover:not(:disabled) {
		background: var(--color-primary-hover);
	}
	.actions button:disabled {
		opacity: 0.5;
	}
	.saved-msg {
		font-size: var(--font-size-md);
		color: var(--color-success);
	}
	.about {
		margin-top: 2.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border-subtle);
	}
	.about h2 {
		font-size: var(--font-size-base);
		font-weight: 600;
		margin: 0 0 0.75rem;
		color: var(--color-text-secondary);
	}
	.about p {
		margin: 0.3rem 0;
		font-size: var(--font-size-sm);
		color: var(--color-text-subtitle);
	}
	.about-name {
		font-weight: 600;
		color: var(--color-text);
	}
	.about-version {
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.about a {
		color: var(--color-primary);
		text-decoration: none;
	}
	.about a:hover {
		text-decoration: underline;
	}
</style>
