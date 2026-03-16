<script lang="ts">
	import { onMount } from 'svelte';
	import AddEpisodeForm from '$lib/components/AddEpisodeForm.svelte';
	import QueueList from '$lib/components/QueueList.svelte';
	import DownloadedList from '$lib/components/DownloadedList.svelte';
	import DeviceOnlyList from '$lib/components/DeviceOnlyList.svelte';
	import GarminStatusStrip from '$lib/components/GarminStatusStrip.svelte';
	import ProgressPanel from '$lib/components/ProgressPanel.svelte';
	import SpaceManagementDialog from '$lib/components/SpaceManagementDialog.svelte';
	import FeedSidebar from '$lib/components/FeedSidebar.svelte';
	import FeedView from '$lib/components/FeedView.svelte';
	import PlaylistGrid from '$lib/components/PlaylistGrid.svelte';
	import AuthModal from '$lib/components/AuthModal.svelte';
	import { getLibrary, refreshLibrary, startProcessing, getAuthStatus, disconnectAuth, listSubscriptions, listHomeFeed, listLikedVideos, listPlaylistVideos } from '$lib/stores/library.svelte';
	import { getGarminStatus, refreshGarmin, transferUnsynced } from '$lib/stores/garmin.svelte';
	import { getProgress, setActive, initProgressListener } from '$lib/stores/progress.svelte';
	import { getTheme, toggleTheme } from '$lib/stores/theme.svelte';
	import { getSettings, refreshSettings } from '$lib/stores/settings.svelte';
	import type { FeedView as FeedViewType, AuthStatus } from '$lib/types';

	const library = getLibrary();
	const theme = getTheme();
	const settings = getSettings();
	const garmin = getGarminStatus();
	const progress = getProgress();

	let transferring = $state(false);
	let searchResultsVisible = $state(false);
	let twoColumnClosing = $state(false);
	let prevSearchVisible = false;

	let activeView = $state<FeedViewType>('search');
	let authStatus = $state<AuthStatus>({ method: null, detail: null });
	let authModalOpen = $state(false);
	let sidebarOpen = $state(false);
	let playlistDetailId = $state('');
	let playlistDetailTitle = $state('');

	$effect(() => {
		if (prevSearchVisible && !searchResultsVisible) {
			twoColumnClosing = true;
			setTimeout(() => { twoColumnClosing = false; }, 300);
		}
		prevSearchVisible = searchResultsVisible;
	});

	onMount(() => {
		let interval: ReturnType<typeof setInterval> | undefined;
		const unlisten = initProgressListener();

		(async () => {
			await Promise.all([refreshLibrary(), refreshGarmin(), refreshSettings()]);
			interval = setInterval(refreshGarmin, 5000);
			try {
				authStatus = await getAuthStatus();
			} catch { /* not connected */ }
		})();

		return () => {
			unlisten();
			if (interval) clearInterval(interval);
		};
	});

	function handleSyncAll() {
		startProcessing();
	}

	async function handleTransfer() {
		transferring = true;
		setActive(true);
		try {
			await transferUnsynced();
			await refreshLibrary();
		} finally {
			transferring = false;
			setActive(false);
		}
	}

	function handleAuthRequired() {
		authModalOpen = true;
	}

	async function handleAuthSuccess() {
		try {
			authStatus = await getAuthStatus();
		} catch { /* ignore */ }
	}

	async function handleDisconnect() {
		await disconnectAuth();
		authStatus = { method: null, detail: null };
		activeView = 'search';
	}

	function handleSelectPlaylist(playlistId: string, title: string) {
		playlistDetailId = playlistId;
		playlistDetailTitle = title;
		activeView = 'playlist-detail';
	}

	function feedFetcher(view: FeedViewType) {
		switch (view) {
			case 'subscriptions': return listSubscriptions;
			case 'home': return listHomeFeed;
			case 'liked': return listLikedVideos;
			case 'playlist-detail': return (offset: number) => listPlaylistVideos(playlistDetailId, offset);
			default: return listSubscriptions;
		}
	}

	const feedTitles: Record<string, string> = {
		subscriptions: 'Subscriptions',
		home: 'Home',
		liked: 'Liked Videos',
	};

	let layoutWidthPercent = $derived(settings.data.search_layout_width_percent ?? 75);
	let layoutSplitPercent = $derived(settings.data.search_layout_split_percent ?? 50);
	let colLeftFlex = $derived(`${layoutWidthPercent * layoutSplitPercent / 100}%`);
	let colRightFlex = $derived(`${layoutWidthPercent * (100 - layoutSplitPercent) / 100}%`);

	let unsyncedCount = $derived.by(() => {
		if (!garmin.data.connected) {
			return library.data.downloaded.filter((e) => e.synced_at === null).length;
		}
		const onWatch = new Set(garmin.data.episodes.map((e) => e.folder_name));
		return library.data.downloaded.filter((e) => !onWatch.has(e.folder_name)).length;
	});

	const showFeedContent = $derived(activeView !== 'search');
</script>

<header class="toolbar">
	<div class="toolbar-left">
		<button
			class="hamburger-btn"
			onclick={() => { sidebarOpen = !sidebarOpen; }}
			aria-label="Toggle sidebar"
		>
			{'\u2630'}
		</button>
		<div class="toolbar-title">
			<h1>youtube-audio-chunker</h1>
			<span class="toolbar-subtitle">Tested with Garmin Forerunner 245 Music</span>
		</div>
	</div>
	<div class="toolbar-actions">
		<button
			onclick={handleSyncAll}
			disabled={library.processing || library.data.queue.length === 0}
		>
			{library.processing ? 'Syncing...' : 'Sync All'}
		</button>
		<button
			onclick={handleTransfer}
			disabled={transferring || unsyncedCount === 0}
		>
			{transferring ? 'Transferring...' : `Transfer Unsynced (${unsyncedCount})`}
		</button>
		<button class="theme-toggle" onclick={toggleTheme}>
			{theme.isDark ? '\u2600' : '\u263E'}
		</button>
	</div>
</header>

<GarminStatusStrip status={garmin.data} />

<div class="app-layout" class:sidebar-mobile-open={sidebarOpen}>
	<FeedSidebar
		bind:activeView
		{authStatus}
		onConnectClick={handleAuthRequired}
		onDisconnectClick={handleDisconnect}
	/>

	{#if sidebarOpen}
		<button class="sidebar-overlay" onclick={() => { sidebarOpen = false; }} aria-label="Close sidebar"></button>
	{/if}

	<div
		class="main-content"
		class:two-column={showFeedContent || searchResultsVisible || twoColumnClosing}
		class:two-column-closing={twoColumnClosing && !showFeedContent}
		style:--col-left={colLeftFlex}
		style:--col-right={colRightFlex}
	>
		{#if showFeedContent}
			<div class="feed-column">
				{#if activeView === 'playlists'}
					<PlaylistGrid
						{authStatus}
						onSelectPlaylist={handleSelectPlaylist}
						onAuthRequired={handleAuthRequired}
					/>
				{:else if activeView === 'playlist-detail'}
					<div class="playlist-detail-header">
						<button class="back-btn" onclick={() => { activeView = 'playlists'; }}>
							&larr; Playlists
						</button>
						<span class="playlist-detail-title">{playlistDetailTitle}</span>
					</div>
					{#key playlistDetailId}
						<FeedView
							title={playlistDetailTitle}
							{authStatus}
							fetchFeed={feedFetcher('playlist-detail')}
							onAuthRequired={handleAuthRequired}
						/>
					{/key}
				{:else}
					{#key activeView}
						<FeedView
							title={feedTitles[activeView] ?? activeView}
							{authStatus}
							fetchFeed={feedFetcher(activeView)}
							onAuthRequired={handleAuthRequired}
						/>
					{/key}
				{/if}
			</div>
		{:else}
			<AddEpisodeForm bind:hasResults={searchResultsVisible} />
		{/if}

		<div class="episode-scroll">
			<QueueList entries={library.data.queue} />
			<DownloadedList episodes={library.data.downloaded} />
			{#if garmin.data.connected}
				<DeviceOnlyList
					garminEpisodes={garmin.data.episodes}
					downloadedEpisodes={library.data.downloaded}
				/>
			{/if}
		</div>
	</div>
</div>

<footer class="app-footer">
	Built by <a href="https://www.tonykwok.info/" target="_blank" rel="noopener">Tony Kwok</a>
</footer>

<ProgressPanel />
<SpaceManagementDialog />
<AuthModal bind:open={authModalOpen} onSuccess={handleAuthSuccess} />

<style>
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		box-shadow: var(--shadow-toolbar);
		background: var(--color-bg-panel);
		flex-shrink: 0;
		z-index: 2;
	}
	.toolbar-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.hamburger-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		cursor: pointer;
		font-size: var(--font-size-lg);
		padding: 0.35rem 0.5rem;
		line-height: 1;
		color: inherit;
		transition: all 0.15s;
	}
	.hamburger-btn:hover {
		background: var(--color-bg-hover);
	}
	@media (min-width: 900px) {
		.hamburger-btn {
			display: none;
		}
	}
	.toolbar-title {
		display: flex;
		flex-direction: column;
	}
	h1 {
		font-size: var(--font-size-lg);
		font-weight: 600;
		margin: 0;
	}
	.toolbar-subtitle {
		font-size: var(--font-size-xs);
		color: var(--color-text-muted);
	}
	.toolbar-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.toolbar-actions button:not(.theme-toggle) {
		font-size: var(--font-size-md);
		padding: 0.45rem 0.75rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-md);
		background: var(--color-primary);
		color: #fff;
		cursor: pointer;
		white-space: nowrap;
		transition: all 0.15s;
	}
	.toolbar-actions button:not(.theme-toggle):hover:not(:disabled) {
		background: var(--color-primary-hover);
	}
	.toolbar-actions button:not(.theme-toggle):disabled {
		opacity: 0.5;
		cursor: default;
	}
	/* App layout with sidebar */
	.app-layout {
		display: flex;
		flex: 1;
		overflow: hidden;
	}
	.app-layout > :global(.feed-sidebar) {
		display: none;
	}
	@media (min-width: 900px) {
		.app-layout > :global(.feed-sidebar) {
			display: flex;
		}
	}
	/* Mobile sidebar overlay */
	.sidebar-mobile-open > :global(.feed-sidebar) {
		display: flex !important;
		position: fixed;
		top: 0;
		left: 0;
		bottom: 0;
		z-index: 50;
		box-shadow: 4px 0 16px rgba(0, 0, 0, 0.2);
	}
	.sidebar-overlay {
		display: none;
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 49;
		border: none;
		cursor: default;
	}
	.sidebar-mobile-open .sidebar-overlay {
		display: block;
	}

	.main-content {
		display: flex;
		flex-direction: column;
		flex: 1;
		overflow: hidden;
		min-width: 0;
		background: var(--color-bg-panel);
		align-items: center;
	}
	.main-content > :global(*) {
		width: 100%;
		max-width: 700px;
	}

	.feed-column {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-height: 0;
	}
	.playlist-detail-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		flex-shrink: 0;
	}
	.back-btn {
		font-size: var(--font-size-sm);
		padding: 0.15rem 0.4rem;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		color: var(--color-text-secondary);
		cursor: pointer;
		transition: all 0.15s;
	}
	.back-btn:hover {
		background: var(--color-bg-hover);
	}
	.playlist-detail-title {
		font-size: var(--font-size-sm);
		font-weight: 600;
		color: var(--color-text-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.episode-scroll {
		flex: 1;
		overflow-y: auto;
	}

	@media (min-width: 750px) {
		.main-content.two-column {
			flex-direction: row;
			align-items: stretch;
			justify-content: center;
			gap: 1rem;
			padding: 0 1rem;
		}
		.main-content.two-column > :global(:first-child) {
			max-width: none;
			flex: 0 1 var(--col-left, 37.5%);
			min-width: 0;
			animation: slide-left 0.3s ease-out;
		}
		.main-content.two-column > :global(:last-child) {
			max-width: none;
			flex: 0 1 var(--col-right, 37.5%);
			min-width: 0;
			animation: slide-right 0.3s ease-out;
		}
		.main-content.two-column > :global(.episode-scroll) {
			overflow-y: auto;
		}
		.main-content.two-column-closing > :global(:first-child) {
			animation: slide-left-out 0.3s ease-in forwards;
		}
		.main-content.two-column-closing > :global(:last-child) {
			animation: slide-right-out 0.3s ease-in forwards;
		}
	}

	@keyframes slide-left-out {
		to {
			opacity: 0;
			transform: translateX(40%);
		}
	}

	@keyframes slide-right-out {
		to {
			opacity: 0;
			transform: translateX(-40%);
		}
	}

	@keyframes slide-left {
		from {
			opacity: 0;
			transform: translateX(40%);
		}
	}

	@keyframes slide-right {
		from {
			opacity: 0;
			transform: translateX(-40%);
		}
	}
	.app-footer {
		flex-shrink: 0;
		text-align: center;
		padding: 0.4rem;
		font-size: var(--font-size-xs);
		color: var(--color-text-muted);
		border-top: 1px solid var(--color-border-subtle);
		background: var(--color-bg-panel);
	}
	.app-footer a {
		color: var(--color-text-hint);
		text-decoration: none;
	}
	.app-footer a:hover {
		color: var(--color-primary);
		text-decoration: underline;
	}
</style>
