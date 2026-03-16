<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { addToQueue, startProcessing, searchYouTube, listChannelVideos, getLibrary } from '$lib/stores/library.svelte';
	import { getSettings, refreshSettings } from '$lib/stores/settings.svelte';
	import { getGarminStatus } from '$lib/stores/garmin.svelte';
	import ContentTypeSelect from './ContentTypeSelect.svelte';
	import type { ContentType, SearchResult, ChannelVideo } from '$lib/types';
	import { formatDuration } from '$lib/format';

	let { hasResults = $bindable(false) }: { hasResults?: boolean } = $props();

	const settings = getSettings();
	const garmin = getGarminStatus();
	const lib = getLibrary();

	function videoLibraryStatus(videoId: string): { status: 'queued' | 'downloaded' | 'synced'; tooltip: string } | null {
		if (lib.data.queue.some(q => q.video_id === videoId)) {
			return { status: 'queued', tooltip: 'In queue' };
		}
		const episode = lib.data.downloaded.find(d => d.video_id === videoId);
		if (!episode) return null;
		if (episode.synced_at) return { status: 'synced', tooltip: 'On watch' };
		return { status: 'downloaded', tooltip: 'Downloaded' };
	}

	let urlInput = $state('');
	let contentType = $state<ContentType>('podcast');
	let submitting = $state(false);
	let errorMsg = $state('');

	let searchResults = $state<SearchResult[]>([]);
	let channelVideos = $state<ChannelVideo[]>([]);
	let channelName = $state('');
	let searching = $state(false);
	let loadingChannel = $state(false);
	let selectedUrls = $state<Set<string>>(new Set());
	let resultsView = $state<'search' | 'channel'>('search');
	let hasMore = $state(false);
	let loadingMore = $state(false);
	let lastSearchQuery = $state('');
	let lastChannelUrl = $state('');

	const resultsVisible = $derived(
		resultsView === 'search' ? searchResults.length > 0 : channelVideos.length > 0
	);

	$effect(() => {
		hasResults = resultsVisible || loadingChannel;
	});

	onMount(async () => {
		await refreshSettings();
		contentType = (settings.data.default_content_type as ContentType) ?? 'podcast';
	});

	function looksLikeUrl(input: string): boolean {
		const trimmed = input.trim();
		return (
			trimmed.startsWith('http://') ||
			trimmed.startsWith('https://') ||
			trimmed.includes('youtube.com') ||
			trimmed.includes('youtu.be')
		);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	}

	async function handleSubmit() {
		const input = urlInput.trim();
		if (!input) return;

		if (looksLikeUrl(input)) {
			await handleUrlSubmit();
		} else {
			await handleSearch(input);
		}
	}

	async function handleUrlSubmit() {
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
			startProcessing({ noTransfer: !garmin.data.connected });
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			submitting = false;
		}
	}

	async function handleSearch(query: string) {
		searching = true;
		errorMsg = '';
		selectedUrls = new Set();
		channelVideos = [];
		channelName = '';
		resultsView = 'search';
		try {
			const results = await searchYouTube(query);
			searchResults = results;
			lastSearchQuery = query;
			hasMore = results.length >= 10;
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			searching = false;
		}
	}

	async function handleBrowseChannel(channelUrl: string) {
		if (!channelUrl) return;
		loadingChannel = true;
		errorMsg = '';
		selectedUrls = new Set();
		try {
			const result = await listChannelVideos(channelUrl);
			channelName = result.channel_name;
			channelVideos = result.videos;
			lastChannelUrl = channelUrl;
			hasMore = result.videos.length >= 10;
			resultsView = 'channel';
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			loadingChannel = false;
		}
	}

	let sentinelEl = $state<HTMLElement | null>(null);
	let observer: IntersectionObserver | null = null;

	$effect(() => {
		observer?.disconnect();
		if (!sentinelEl || !hasMore || loadingMore) return;
		observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					loadMoreResults();
				}
			},
			{ rootMargin: '100px' }
		);
		observer.observe(sentinelEl);
	});

	onDestroy(() => observer?.disconnect());

	async function loadMoreResults() {
		if (loadingMore || !hasMore) return;
		loadingMore = true;
		try {
			if (resultsView === 'search') {
				const more = await searchYouTube(lastSearchQuery, searchResults.length);
				searchResults = [...searchResults, ...more];
				hasMore = more.length >= 10;
			} else {
				const result = await listChannelVideos(lastChannelUrl, channelVideos.length);
				channelVideos = [...channelVideos, ...result.videos];
				hasMore = result.videos.length >= 10;
			}
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			loadingMore = false;
		}
	}

	function handleToggleResult(url: string) {
		const next = new Set(selectedUrls);
		if (next.has(url)) {
			next.delete(url);
		} else {
			next.add(url);
		}
		selectedUrls = next;
	}

	async function handleAddSelected() {
		if (selectedUrls.size === 0) return;
		submitting = true;
		errorMsg = '';
		try {
			const result = await addToQueue([...selectedUrls], contentType);
			if (result.skipped.length > 0 && result.added.length === 0) {
				errorMsg = `Skipped (already exists): ${result.skipped.join(', ')}`;
			} else {
				dismissResults();
				urlInput = '';
			}
			startProcessing({ noTransfer: !garmin.data.connected });
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			submitting = false;
		}
	}

	function handleBackToSearch() {
		channelVideos = [];
		channelName = '';
		selectedUrls = new Set();
		hasMore = searchResults.length >= 10;
		resultsView = 'search';
	}

	function dismissResults() {
		searchResults = [];
		channelVideos = [];
		channelName = '';
		selectedUrls = new Set();
		resultsView = 'search';
	}

	const buttonLabel = $derived(
		searching ? 'Searching...'
		: submitting ? 'Adding...'
		: looksLikeUrl(urlInput) ? '+ Add'
		: 'Search'
	);

	const buttonDisabled = $derived(
		submitting || searching || urlInput.trim().length === 0
	);
</script>

<div class="add-episode-container">
<form class="add-form" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
	<textarea
		bind:value={urlInput}
		placeholder="Paste YouTube URL(s) or search..."
		rows="1"
		disabled={submitting || searching}
		onkeydown={handleKeydown}
	></textarea>
	<div class="form-row">
		<ContentTypeSelect bind:value={contentType} disabled={submitting || searching} />
		<button class="btn btn-primary" type="submit" disabled={buttonDisabled}>
			{buttonLabel}
		</button>
		{#if resultsVisible || loadingChannel}
			<button type="button" class="btn btn-sm btn-outline" onclick={dismissResults}>&times; Close</button>
		{/if}
	</div>
	{#if errorMsg}
		<div class="error">{errorMsg}</div>
	{/if}
</form>

{#if resultsVisible || loadingChannel}
	<div class="search-results">
		<div class="results-header">
			{#if resultsView === 'channel'}
				<button class="btn btn-sm btn-outline" onclick={handleBackToSearch} disabled={loadingChannel}>
					&larr; Back
				</button>
				<span class="results-title">{channelName}</span>
			{:else}
				<span class="results-title">Search results ({searchResults.length})</span>
			{/if}
			{#if selectedUrls.size > 0}
				<div class="header-actions">
					<button class="btn btn-sm btn-primary" onclick={handleAddSelected} disabled={submitting}>
						Add ({selectedUrls.size})
					</button>
				</div>
			{/if}
		</div>

		{#if loadingChannel}
			<div class="results-loading">Loading channel...</div>
		{:else if resultsView === 'search'}
			{#each searchResults as result}
				{@const libStatus = videoLibraryStatus(result.video_id)}
				<label class="result-row" class:selected={selectedUrls.has(result.url)}>
					{#if libStatus}
						<span class="status-tooltip">
							<span class="status-dot {libStatus.status}"></span>
							{libStatus.tooltip}
						</span>
					{/if}
					<input
						type="checkbox"
						class="result-checkbox"
						checked={selectedUrls.has(result.url)}
						onchange={() => handleToggleResult(result.url)}
					/>
					<div class="result-info">
						<div class="result-title" title={result.title}>{result.title}</div>
						<div class="result-meta">
							{#if result.channel_url}
								<button
									class="channel-link"
									onclick={(e) => { e.preventDefault(); e.stopPropagation(); handleBrowseChannel(result.channel_url); }}
									disabled={loadingChannel}
								>{result.channel}</button>
							{:else}
								<span class="channel-name">{result.channel}</span>
							{/if}
							<span class="result-duration">{formatDuration(result.duration_seconds)}</span>
							{#if libStatus}
								<span class="library-badge {libStatus.status}">{libStatus.tooltip}</span>
							{/if}
						</div>
					</div>
				</label>
			{/each}
			{#if loadingMore}
				<div class="load-more-hint">Loading more...</div>
			{/if}
			{#if hasMore}
				<div bind:this={sentinelEl} class="load-sentinel"></div>
			{/if}
		{:else}
			{#each channelVideos as video}
				{@const libStatus = videoLibraryStatus(video.video_id)}
				<label class="result-row" class:selected={selectedUrls.has(video.url)}>
					{#if libStatus}
						<span class="status-tooltip">
							<span class="status-dot {libStatus.status}"></span>
							{libStatus.tooltip}
						</span>
					{/if}
					<input
						type="checkbox"
						class="result-checkbox"
						checked={selectedUrls.has(video.url)}
						onchange={() => handleToggleResult(video.url)}
					/>
					<div class="result-info">
						<div class="result-title" title={video.title}>{video.title}</div>
						<div class="result-meta">
							<span class="result-duration">{formatDuration(video.duration_seconds)}</span>
							{#if libStatus}
								<span class="library-badge {libStatus.status}">{libStatus.tooltip}</span>
							{/if}
						</div>
					</div>
				</label>
			{/each}
			{#if loadingMore}
				<div class="load-more-hint">Loading more...</div>
			{/if}
			{#if hasMore}
				<div bind:this={sentinelEl} class="load-sentinel"></div>
			{/if}
		{/if}
	</div>
{/if}
</div>

<style>
	.add-episode-container {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}
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
	.error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		margin-top: 0.3rem;
	}

	/* Search results panel */
	.search-results {
		border-bottom: 1px solid var(--color-border-subtle);
		overflow-y: auto;
		flex: 1;
		min-height: 0;
	}
	.results-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
	}
	.results-title {
		font-size: var(--font-size-sm);
		font-weight: 600;
		color: var(--color-text-secondary);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex-shrink: 0;
	}
	.results-loading {
		padding: 0.75rem;
		text-align: center;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
	.result-row {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.4rem 0.75rem;
		cursor: pointer;
		transition: background 0.1s;
		position: relative;
	}
	.result-row:hover {
		background: var(--color-bg-hover);
	}
	.result-row.selected {
		background: var(--color-primary-light);
	}
	.status-tooltip {
		display: none;
		position: absolute;
		left: -2px;
		top: -6px;
		transform: translateY(-100%);
		background: var(--color-bg-panel);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-sm);
		padding: 0.2rem 0.45rem;
		font-size: var(--font-size-xs);
		color: var(--color-text-secondary);
		white-space: nowrap;
		align-items: center;
		gap: 0.3rem;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
		z-index: 10;
		pointer-events: none;
	}
	.result-row:hover .status-tooltip {
		display: flex;
	}
	.status-dot {
		width: 7px;
		height: 7px;
		border-radius: var(--radius-full);
		flex-shrink: 0;
	}
	.status-dot.synced {
		background: var(--color-card-synced);
	}
	.status-dot.queued {
		background: var(--color-card-queued);
	}
	.status-dot.downloaded {
		background: var(--color-text-muted);
	}
	.library-badge {
		font-size: var(--font-size-xs);
		padding: 0.05rem 0.35rem;
		border-radius: var(--radius-full);
		white-space: nowrap;
		flex-shrink: 0;
	}
	.library-badge.synced {
		background: color-mix(in srgb, var(--color-card-synced) 15%, transparent);
		color: var(--color-card-synced);
	}
	.library-badge.queued {
		background: color-mix(in srgb, var(--color-card-queued) 15%, transparent);
		color: var(--color-card-queued);
	}
	.library-badge.downloaded {
		background: color-mix(in srgb, var(--color-text-muted) 15%, transparent);
		color: var(--color-text-secondary);
	}
	.result-checkbox {
		margin-top: 0.2rem;
		flex-shrink: 0;
		cursor: pointer;
	}
	.result-info {
		flex: 1;
		min-width: 0;
	}
	.result-title {
		font-size: var(--font-size-md);
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.result-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		margin-top: 0.1rem;
	}
	.channel-link {
		font-size: var(--font-size-sm);
		padding: 0;
		background: none;
		border: none;
		color: var(--color-primary);
		cursor: pointer;
		text-decoration: none;
	}
	.channel-link:hover:not(:disabled) {
		text-decoration: underline;
		background: none;
	}
	.channel-name {
		color: var(--color-text-muted);
	}
	.result-duration {
		color: var(--color-text-hint);
		flex-shrink: 0;
	}
	.load-more-hint {
		padding: 0.4rem 0.75rem;
		text-align: center;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
	.load-sentinel {
		height: 1px;
	}
</style>
