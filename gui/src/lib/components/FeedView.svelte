<script lang="ts">
	import { onDestroy } from 'svelte';
	import { addToQueue, startProcessing, getLibrary } from '$lib/stores/library.svelte';
	import { getSettings, refreshSettings } from '$lib/stores/settings.svelte';
	import { getGarminStatus } from '$lib/stores/garmin.svelte';
	import ContentTypeSelect from './ContentTypeSelect.svelte';
	import type { ContentType, SearchResult, AuthStatus } from '$lib/types';
	import { formatDuration } from '$lib/format';

	let {
		title,
		authStatus,
		fetchFeed,
		onAuthRequired,
	}: {
		title: string;
		authStatus: AuthStatus;
		fetchFeed: (offset: number) => Promise<SearchResult[]>;
		onAuthRequired: () => void;
	} = $props();

	const settings = getSettings();
	const garmin = getGarminStatus();
	const lib = getLibrary();

	let results = $state<SearchResult[]>([]);
	let loading = $state(false);
	let errorMsg = $state('');
	let hasMore = $state(false);
	let loadingMore = $state(false);
	let selectedUrls = $state<Set<string>>(new Set());
	let submitting = $state(false);
	let contentType = $state<ContentType>('podcast');
	let initialized = $state(false);

	function videoLibraryStatus(videoId: string): { status: 'queued' | 'downloaded' | 'synced'; tooltip: string } | null {
		if (lib.data.queue.some(q => q.video_id === videoId)) {
			return { status: 'queued', tooltip: 'In queue' };
		}
		const episode = lib.data.downloaded.find(d => d.video_id === videoId);
		if (!episode) return null;
		if (episode.synced_at) return { status: 'synced', tooltip: 'On watch' };
		return { status: 'downloaded', tooltip: 'Downloaded' };
	}

	$effect(() => {
		// Re-load when authStatus changes and we have auth
		if (authStatus.method && !initialized) {
			loadFeed();
		}
	});

	async function loadFeed() {
		if (!authStatus.method) {
			onAuthRequired();
			return;
		}
		loading = true;
		errorMsg = '';
		results = [];
		selectedUrls = new Set();
		initialized = true;
		contentType = (settings.data.default_content_type as ContentType) ?? 'podcast';
		try {
			const data = await fetchFeed(0);
			results = data;
			hasMore = data.length >= 10;
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			loading = false;
		}
	}

	let sentinelEl = $state<HTMLElement | null>(null);
	let observer: IntersectionObserver | null = null;

	$effect(() => {
		observer?.disconnect();
		if (!sentinelEl || !hasMore || loadingMore) return;
		observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) loadMoreResults();
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
			const more = await fetchFeed(results.length);
			results = [...results, ...more];
			hasMore = more.length >= 10;
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			loadingMore = false;
		}
	}

	function handleToggleResult(url: string) {
		const next = new Set(selectedUrls);
		if (next.has(url)) next.delete(url);
		else next.add(url);
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
				selectedUrls = new Set();
			}
			startProcessing({ noTransfer: !garmin.data.connected });
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			submitting = false;
		}
	}

</script>

<div class="feed-view">
	<div class="feed-header">
		<span class="feed-title">{title}</span>
		{#if selectedUrls.size > 0}
			<div class="feed-actions">
				<ContentTypeSelect bind:value={contentType} disabled={submitting} />
				<button class="btn btn-primary" onclick={handleAddSelected} disabled={submitting}>
					Add ({selectedUrls.size})
				</button>
			</div>
		{/if}
		<button class="btn btn-outline" onclick={loadFeed} disabled={loading}>
			{loading ? 'Loading...' : 'Refresh'}
		</button>
	</div>

	{#if errorMsg}
		<div class="feed-error">{errorMsg}</div>
	{/if}

	{#if loading && results.length === 0}
		<div class="feed-loading">Loading {title.toLowerCase()}...</div>
	{:else if !initialized}
		<div class="feed-empty">
			<button class="btn btn-primary" onclick={loadFeed}>Load {title}</button>
		</div>
	{:else if results.length === 0}
		<div class="feed-empty">No videos found</div>
	{:else}
		<div class="feed-results">
			{#each results as result}
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
							<span class="channel-name">{result.channel}</span>
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
		</div>
	{/if}
</div>

<style>
	.feed-view {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		flex: 1;
	}
	.feed-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		flex-shrink: 0;
	}
	.feed-title {
		font-size: var(--font-size-md);
		font-weight: 600;
		color: var(--color-text-secondary);
		flex: 1;
	}
	.feed-actions {
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}
	.feed-error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		padding: 0.3rem 0.75rem;
	}
	.feed-loading, .feed-empty {
		padding: 2rem 0.75rem;
		text-align: center;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
	.feed-results {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
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
	.status-dot.synced { background: var(--color-card-synced); }
	.status-dot.queued { background: var(--color-card-queued); }
	.status-dot.downloaded { background: var(--color-text-muted); }
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
