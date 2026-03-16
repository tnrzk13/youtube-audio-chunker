<script lang="ts">
	import { onMount } from 'svelte';
	import { addToQueue, startProcessing, getLibrary } from '$lib/stores/library.svelte';
	import { getSettings } from '$lib/stores/settings.svelte';
	import { getGarminStatus } from '$lib/stores/garmin.svelte';
	import {
		getDiscoverState,
		selectTopic,
		refreshTopics,
		searchTopic,
		createTopic,
		updateTopic,
		deleteTopic,
		dismissVideo,
		extractTopics,
	} from '$lib/stores/discover.svelte';
	import ContentTypeSelect from './ContentTypeSelect.svelte';
	import type { ContentType, Topic } from '$lib/types';
	import { formatDuration } from '$lib/format';

	const discover = getDiscoverState();
	const settings = getSettings();
	const garmin = getGarminStatus();
	const lib = getLibrary();

	let newTopicName = $state('');
	let newTopicQuery = $state('');
	let editingTopicId = $state<string | null>(null);
	let editName = $state('');
	let editQuery = $state('');
	let errorMsg = $state('');
	let contentType = $state<ContentType>('podcast');
	let selectedUrls = $state<Set<string>>(new Set());
	let submitting = $state(false);

	onMount(() => {
		refreshTopics();
		contentType = (settings.data.default_content_type as ContentType) ?? 'podcast';
	});

	async function handleCreateTopic() {
		if (!newTopicName.trim()) return;
		const query = newTopicQuery.trim() || newTopicName.trim();
		await createTopic(newTopicName.trim(), query);
		newTopicName = '';
		newTopicQuery = '';
	}

	async function handleSelectTopic(topic: Topic) {
		selectTopic(topic);
		errorMsg = '';
		try {
			await searchTopic(topic.id);
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		}
	}

	function handleBack() {
		selectTopic(null);
		errorMsg = '';
		selectedUrls = new Set();
	}

	async function handleLoadMore() {
		if (!discover.selectedTopic || !discover.nextPageToken) return;
		try {
			await searchTopic(discover.selectedTopic.id, discover.nextPageToken);
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		}
	}

	function startEditTopic(topic: Topic) {
		editingTopicId = topic.id;
		editName = topic.name;
		editQuery = topic.search_query;
	}

	async function saveEditTopic() {
		if (!editingTopicId) return;
		await updateTopic(editingTopicId, editName, editQuery);
		editingTopicId = null;
	}

	function cancelEditTopic() {
		editingTopicId = null;
	}

	async function handleDeleteTopic(topicId: string) {
		await deleteTopic(topicId);
	}

	async function handleDismiss(videoId: string) {
		await dismissVideo(videoId);
	}

	async function handleExtract() {
		errorMsg = '';
		try {
			await extractTopics();
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
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
			await addToQueue([...selectedUrls], contentType);
			selectedUrls = new Set();
			startProcessing({ noTransfer: !garmin.data.connected });
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			submitting = false;
		}
	}

	function videoLibraryStatus(videoId: string): { status: 'queued' | 'downloaded' | 'synced'; tooltip: string } | null {
		if (lib.data.queue.some(q => q.video_id === videoId)) {
			return { status: 'queued', tooltip: 'In queue' };
		}
		const episode = lib.data.downloaded.find(d => d.video_id === videoId);
		if (!episode) return null;
		if (episode.synced_at) return { status: 'synced', tooltip: 'On watch' };
		return { status: 'downloaded', tooltip: 'Downloaded' };
	}
</script>

<div class="discover-view">
	{#if discover.selectedTopic}
		<!-- Topic results view -->
		<div class="discover-header">
			<button class="btn btn-sm btn-outline" onclick={handleBack}>&larr; Topics</button>
			<span class="discover-title">{discover.selectedTopic.name}</span>
			{#if selectedUrls.size > 0}
				<div class="discover-actions">
					<ContentTypeSelect bind:value={contentType} disabled={submitting} />
					<button class="btn btn-primary" onclick={handleAddSelected} disabled={submitting}>
						Add ({selectedUrls.size})
					</button>
				</div>
			{/if}
		</div>

		{#if errorMsg}
			<div class="discover-error">{errorMsg}</div>
		{/if}

		{#if discover.loading && discover.results.length === 0}
			<div class="discover-loading">Searching YouTube...</div>
		{:else if discover.results.length === 0}
			<div class="discover-empty">No results found</div>
		{:else}
			<div class="discover-results">
				{#each discover.results as result}
					{@const libStatus = videoLibraryStatus(result.video_id)}
					<div class="result-row" class:selected={selectedUrls.has(result.url)}>
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
								{#if result.duration_seconds}
									<span class="result-duration">{formatDuration(result.duration_seconds)}</span>
								{/if}
								{#if libStatus}
									<span class="library-badge {libStatus.status}">{libStatus.tooltip}</span>
								{/if}
							</div>
						</div>
						<button
							class="btn-icon dismiss-btn"
							onclick={() => handleDismiss(result.video_id)}
							title="Not interested"
						>
							&times;
						</button>
					</div>
				{/each}
				{#if discover.loading}
					<div class="load-more-hint">Loading more...</div>
				{/if}
				{#if discover.nextPageToken && !discover.loading}
					<button class="load-more-btn" onclick={handleLoadMore}>
						Load more
					</button>
				{/if}
			</div>
		{/if}
	{:else}
		<!-- Topic list view -->
		<div class="discover-header">
			<span class="discover-title">Discover</span>
			<button
				class="btn btn-sm btn-outline"
				onclick={handleExtract}
				disabled={discover.extracting}
			>
				{discover.extracting ? 'Analyzing...' : 'Auto-detect topics'}
			</button>
		</div>

		{#if errorMsg}
			<div class="discover-error">{errorMsg}</div>
		{/if}

		<div class="add-topic-form">
			<input
				type="text"
				bind:value={newTopicName}
				placeholder="Topic name"
				class="topic-input"
			/>
			<input
				type="text"
				bind:value={newTopicQuery}
				placeholder="Search query (optional)"
				class="topic-input"
			/>
			<button class="btn btn-sm btn-primary" onclick={handleCreateTopic} disabled={!newTopicName.trim()}>
				Add
			</button>
		</div>

		{#if discover.topics.length === 0}
			<div class="discover-empty">
				<p>No topics yet</p>
				<p>Add a topic manually or click "Auto-detect topics" to analyze your library</p>
			</div>
		{:else}
			<div class="topic-list">
				{#each discover.topics as topic}
					<div class="topic-card">
						{#if editingTopicId === topic.id}
							<div class="topic-edit-form">
								<input type="text" bind:value={editName} class="topic-input" />
								<input type="text" bind:value={editQuery} class="topic-input" placeholder="Search query" />
								<div class="topic-edit-actions">
									<button class="btn btn-sm btn-primary" onclick={saveEditTopic}>Save</button>
									<button class="btn btn-sm btn-outline" onclick={cancelEditTopic}>Cancel</button>
								</div>
							</div>
						{:else}
							<div class="topic-info">
								<span class="topic-name">{topic.name}</span>
								<span class="topic-query">{topic.search_query}</span>
							</div>
							<div class="topic-actions">
								<button class="btn btn-sm btn-primary" onclick={() => handleSelectTopic(topic)}>
									Explore
								</button>
								<button class="btn btn-sm btn-outline" onclick={() => startEditTopic(topic)}>
									Edit
								</button>
								<button class="btn-icon" onclick={() => handleDeleteTopic(topic.id)}>
									&times;
								</button>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<style>
	.discover-view {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		flex: 1;
	}
	.discover-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		flex-shrink: 0;
	}
	.discover-title {
		font-size: var(--font-size-md);
		font-weight: 600;
		color: var(--color-text-secondary);
		flex: 1;
	}
	.discover-actions {
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}
	.discover-error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		padding: 0.3rem 0.75rem;
	}
	.discover-loading, .discover-empty {
		padding: 2rem 0.75rem;
		text-align: center;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
	.discover-empty p {
		margin: 0.3rem 0;
	}

	/* Add topic form */
	.add-topic-form {
		display: flex;
		gap: 0.4rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
	}
	.topic-input {
		flex: 1;
		min-width: 0;
		padding: 0.3rem 0.5rem;
		font-size: var(--font-size-sm);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-panel);
	}
	.topic-input:focus {
		outline: none;
		border-color: var(--color-primary);
	}

	/* Topic list */
	.topic-list {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
	}
	.topic-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		gap: 0.5rem;
		transition: background 0.1s;
	}
	.topic-card:hover {
		background: var(--color-bg-hover);
	}
	.topic-info {
		flex: 1;
		min-width: 0;
	}
	.topic-name {
		display: block;
		font-size: var(--font-size-base);
		font-weight: 500;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.topic-query {
		display: block;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.topic-actions {
		display: flex;
		gap: 0.25rem;
		flex-shrink: 0;
		opacity: 0;
		transition: opacity 0.15s;
	}
	.topic-card:hover .topic-actions {
		opacity: 1;
	}

	/* Topic edit form */
	.topic-edit-form {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		flex: 1;
	}
	.topic-edit-actions {
		display: flex;
		gap: 0.3rem;
	}

	/* Result rows */
	.discover-results {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
	}
	.result-row {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.4rem 0.75rem;
		transition: background 0.1s;
	}
	.result-row:hover {
		background: var(--color-bg-hover);
	}
	.result-row.selected {
		background: var(--color-primary-light);
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
	.dismiss-btn {
		flex-shrink: 0;
		opacity: 0;
	}
	.result-row:hover .dismiss-btn {
		opacity: 1;
	}
	.load-more-hint {
		padding: 0.4rem 0.75rem;
		text-align: center;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
	.load-more-btn {
		display: block;
		width: 100%;
		padding: 0.5rem;
		font-size: var(--font-size-sm);
		border: none;
		background: none;
		color: var(--color-primary);
		cursor: pointer;
		transition: background 0.1s;
	}
	.load-more-btn:hover {
		background: var(--color-bg-hover);
	}
</style>
