<script lang="ts">
	import { onMount } from 'svelte';
	import { getSettings, refreshSettings, saveSettings } from '$lib/stores/settings.svelte';
	import { getTheme, toggleTheme } from '$lib/stores/theme.svelte';
	import { getAuthStatus, disconnectAuth, connectCookies } from '$lib/stores/library.svelte';
	import ContentTypeSelect from '$lib/components/ContentTypeSelect.svelte';
	import type { AuthStatus, ContentType } from '$lib/types';

	const settings = getSettings();
	const theme = getTheme();

	let defaultContentType = $state<ContentType>('podcast');
	let defaultArtist = $state('');
	let searchLayoutWidthPercent = $state(75);
	let searchLayoutSplitPercent = $state(50);
	let saving = $state(false);
	let saved = $state(false);

	let topicProvider = $state('anthropic');
	let topicModel = $state('');
	let anthropicApiKey = $state('');
	let openaiApiKey = $state('');
	let youtubeApiKey = $state('');
	let envKeys = $state<string[]>([]);

	const ANTHROPIC_MODELS = [
		{ value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (fastest, cheapest)' },
		{ value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
		{ value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
	];
	const OPENAI_MODELS = [
		{ value: 'gpt-4o-mini', label: 'GPT-4o Mini (fastest, cheapest)' },
		{ value: 'gpt-4o', label: 'GPT-4o' },
		{ value: 'gpt-4.1', label: 'GPT-4.1' },
		{ value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
	];
	let availableModels = $derived(topicProvider === 'openai' ? OPENAI_MODELS : ANTHROPIC_MODELS);
	let defaultModel = $derived(topicProvider === 'openai' ? 'gpt-4o-mini' : 'claude-haiku-4-5-20251001');

	function handleProviderChange() {
		topicModel = '';
	}

	let authStatus = $state<AuthStatus>({ method: null, detail: null });
	let browserOverride = $state('');
	let disconnecting = $state(false);
	let reconnecting = $state(false);

	onMount(async () => {
		await refreshSettings();
		defaultContentType = (settings.data.default_content_type as ContentType) ?? 'podcast';
		defaultArtist = settings.data.default_artist ?? '';
		searchLayoutWidthPercent = settings.data.search_layout_width_percent ?? 75;
		searchLayoutSplitPercent = settings.data.search_layout_split_percent ?? 50;
		browserOverride = settings.data.youtube_cookies_browser ?? '';
		topicProvider = settings.data.topic_provider ?? 'anthropic';
		topicModel = settings.data.topic_model ?? '';
		envKeys = settings.data._env_keys ?? [];
		anthropicApiKey = envKeys.includes('anthropic_api_key') ? '' : (settings.data.anthropic_api_key ?? '');
		openaiApiKey = envKeys.includes('openai_api_key') ? '' : (settings.data.openai_api_key ?? '');
		youtubeApiKey = envKeys.includes('youtube_api_key') ? '' : (settings.data.youtube_api_key ?? '');
		try {
			authStatus = await getAuthStatus();
		} catch { /* not connected */ }
	});

	async function handleDisconnect() {
		disconnecting = true;
		try {
			await disconnectAuth();
			authStatus = { method: null, detail: null };
		} finally {
			disconnecting = false;
		}
	}

	async function handleBrowserOverride() {
		if (!browserOverride) return;
		reconnecting = true;
		try {
			const result = await connectCookies(browserOverride);
			if (result.success) {
				authStatus = await getAuthStatus();
			}
		} finally {
			reconnecting = false;
		}
	}

	async function handleSave() {
		saving = true;
		saved = false;
		const youtubeFields: Record<string, any> = {};
		if (settings.data.youtube_auth_method) {
			youtubeFields.youtube_auth_method = settings.data.youtube_auth_method;
		}
		if (settings.data.youtube_cookies_browser) {
			youtubeFields.youtube_cookies_browser = settings.data.youtube_cookies_browser;
		}
		if (settings.data.youtube_account_name) {
			youtubeFields.youtube_account_name = settings.data.youtube_account_name;
		}
		if (settings.data.youtube_account_email) {
			youtubeFields.youtube_account_email = settings.data.youtube_account_email;
		}
		await saveSettings({
			default_content_type: defaultContentType,
			default_artist: defaultArtist || undefined,
			search_layout_width_percent: searchLayoutWidthPercent,
			search_layout_split_percent: searchLayoutSplitPercent,
			topic_provider: topicProvider,
			topic_model: topicModel || undefined,
			anthropic_api_key: anthropicApiKey || undefined,
			openai_api_key: openaiApiKey || undefined,
			youtube_api_key: youtubeApiKey || undefined,
			...youtubeFields,
		});
		saving = false;
		saved = true;
		setTimeout(() => { saved = false; }, 2000);
	}
</script>

<header class="toolbar">
	<a href="/" class="toolbar-icon">{'\u2190'}</a>
	<h1>Settings</h1>
	<button class="theme-toggle" onclick={toggleTheme} title={theme.isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
		{theme.isDark ? '\u2600' : '\u263E'}
	</button>
</header>

<main class="settings">
	<div class="field">
		<label for="default-content-type">Default content type</label>
		<ContentTypeSelect id="default-content-type" bind:value={defaultContentType} />
	</div>


	<div class="field">
		<label for="default-artist">Default artist name</label>
		<input id="default-artist" type="text" bind:value={defaultArtist} placeholder="Leave blank to use uploader" />
	</div>


	<h2 class="section-heading">Search Layout</h2>

	<div class="field">
		<label for="layout-width">Two-column width ({searchLayoutWidthPercent}%)</label>
		<input id="layout-width" type="range" bind:value={searchLayoutWidthPercent} min="50" max="100" step="5" />
		<p class="hint">Total width of the two-column layout when search results are visible. Default: 75%.</p>
	</div>

	<div class="field">
		<label for="layout-split">Column split ({searchLayoutSplitPercent}/{100 - searchLayoutSplitPercent})</label>
		<input id="layout-split" type="range" bind:value={searchLayoutSplitPercent} min="20" max="80" step="5" />
		<p class="hint">How much space the search panel takes vs the library panel. Default: 50/50.</p>
	</div>

	<div class="actions">
		<button class="btn btn-primary" onclick={handleSave} disabled={saving}>
			{saving ? 'Saving...' : 'Save'}
		</button>
		{#if saved}
			<span class="saved-msg">Saved</span>
		{/if}
	</div>

	<h2 class="section-heading">API Keys (Discover)</h2>

	<div class="field">
		<label for="topic-provider">Topic extraction provider</label>
		<select id="topic-provider" bind:value={topicProvider} onchange={handleProviderChange}>
			<option value="anthropic">Anthropic (Claude)</option>
			<option value="openai">OpenAI (GPT)</option>
		</select>
		<p class="hint">Which LLM provider to use for auto-detecting topics from your library.</p>
	</div>

	<div class="field">
		<label for="topic-model">Model</label>
		<select id="topic-model" bind:value={topicModel}>
			<option value="">Default ({availableModels[0].label})</option>
			{#each availableModels as model}
				<option value={model.value}>{model.label}</option>
			{/each}
		</select>
	</div>

	{#if topicProvider === 'anthropic'}
		<div class="field">
			<label for="anthropic-key">
				Anthropic API key
				{#if envKeys.includes('anthropic_api_key')}
					<span class="env-badge">from .env</span>
				{/if}
			</label>
			{#if envKeys.includes('anthropic_api_key')}
				<input id="anthropic-key" type="password" bind:value={anthropicApiKey} placeholder="Override .env value..." autocomplete="off" />
			{:else}
				<input id="anthropic-key" type="password" bind:value={anthropicApiKey} placeholder="sk-ant-..." autocomplete="off" />
			{/if}
			<p class="hint">Get one at console.anthropic.com. Or set ANTHROPIC_API_KEY in .env.</p>
		</div>
	{:else}
		<div class="field">
			<label for="openai-key">
				OpenAI API key
				{#if envKeys.includes('openai_api_key')}
					<span class="env-badge">from .env</span>
				{/if}
			</label>
			{#if envKeys.includes('openai_api_key')}
				<input id="openai-key" type="password" bind:value={openaiApiKey} placeholder="Override .env value..." autocomplete="off" />
			{:else}
				<input id="openai-key" type="password" bind:value={openaiApiKey} placeholder="sk-..." autocomplete="off" />
			{/if}
			<p class="hint">Get one at platform.openai.com. Or set OPENAI_API_KEY in .env.</p>
		</div>
	{/if}

	<div class="field">
		<label for="youtube-key">
			YouTube Data API key
			{#if envKeys.includes('youtube_api_key')}
				<span class="env-badge">from .env</span>
			{/if}
		</label>
		{#if envKeys.includes('youtube_api_key')}
			<input id="youtube-key" type="password" bind:value={youtubeApiKey} placeholder="Override .env value..." autocomplete="off" />
		{:else}
			<input id="youtube-key" type="password" bind:value={youtubeApiKey} placeholder="AIza..." autocomplete="off" />
		{/if}
		<p class="hint">Used to search YouTube for topic-related videos. Or set YOUTUBE_API_KEY in .env.</p>
	</div>

	<h2 class="section-heading">YouTube Account</h2>

	{#if authStatus.method}
		<div class="field">
			<div class="auth-status">
				<span class="auth-dot connected"></span>
				Connected via {authStatus.detail}
			</div>
		</div>

		{#if authStatus.method === 'cookies'}
			<div class="field">
				<label for="browser-override">Browser</label>
				<div class="browser-row">
					<select id="browser-override" bind:value={browserOverride}>
						<option value="chrome">Chrome</option>
						<option value="firefox">Firefox</option>
						<option value="chromium">Chromium</option>
						<option value="edge">Edge</option>
						<option value="brave">Brave</option>
					</select>
					<button class="btn btn-sm btn-outline" onclick={handleBrowserOverride} disabled={reconnecting}>
						{reconnecting ? 'Applying...' : 'Apply'}
					</button>
				</div>
				<p class="hint">Override which browser to extract YouTube cookies from.</p>
			</div>
		{/if}

		<div class="field">
			<button class="btn btn-sm btn-outline-danger" onclick={handleDisconnect} disabled={disconnecting}>
				{disconnecting ? 'Signing out...' : 'Sign out'}
			</button>
		</div>
	{:else}
		<div class="field">
			<div class="auth-status">
				<span class="auth-dot"></span>
				Not connected
			</div>
			<p class="hint">Connect from the main page sidebar to browse your YouTube feeds.</p>
		</div>
	{/if}

	<div class="about">
		<h2>About</h2>
		<p class="about-name">youtube-audio-chunker <span class="about-version">v0.1.0</span></p>
		<p class="about-desc">Download YouTube audio and sideload to Garmin watches.</p>
		<p class="about-desc">Tested on Garmin Forerunner 245 Music. Should work with any music-capable Garmin watch.</p>
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
		width: 100%;
		max-width: 680px;
		margin: 0 auto;
		padding: 1.5rem 1rem;
		flex: 1;
		overflow-y: auto;
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
	input[type='text'],
	input[type='password'] {
		width: 100%;
		padding: 0.4rem;
		font-size: var(--font-size-base);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		transition: border-color 0.15s;
	}
	input[type='number']:focus,
	input[type='text']:focus,
	input[type='password']:focus {
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
	.section-heading {
		font-size: var(--font-size-base);
		font-weight: 600;
		margin: 1.5rem 0 0.75rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border-subtle);
		color: var(--color-text-secondary);
	}
	input[type='range'] {
		width: 100%;
		accent-color: var(--color-primary);
	}
	.hint {
		font-size: var(--font-size-sm);
		color: var(--color-text-hint);
		margin: 0.2rem 0 0;
	}
	.env-badge {
		font-size: var(--font-size-xs);
		font-weight: 400;
		color: var(--color-success);
		background: var(--color-success-light);
		padding: 0.1rem 0.35rem;
		border-radius: var(--radius-full);
		margin-left: 0.3rem;
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.saved-msg {
		font-size: var(--font-size-md);
		color: var(--color-success);
	}
	.auth-status {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--font-size-base);
		color: var(--color-text);
	}
	.auth-dot {
		width: 8px;
		height: 8px;
		border-radius: var(--radius-full);
		background: var(--color-text-muted);
		flex-shrink: 0;
	}
	.auth-dot.connected {
		background: var(--color-card-synced);
	}
	.browser-row {
		display: flex;
		gap: 0.4rem;
	}
	.browser-row select {
		flex: 1;
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
