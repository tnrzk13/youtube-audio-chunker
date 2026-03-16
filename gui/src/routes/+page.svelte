<script lang="ts">
	import { onMount } from 'svelte';
	import AddEpisodeForm from '$lib/components/AddEpisodeForm.svelte';
	import QueueList from '$lib/components/QueueList.svelte';
	import DownloadedList from '$lib/components/DownloadedList.svelte';
	import DeviceOnlyList from '$lib/components/DeviceOnlyList.svelte';
	import GarminStatusStrip from '$lib/components/GarminStatusStrip.svelte';
	import ProgressPanel from '$lib/components/ProgressPanel.svelte';
	import SpaceManagementDialog from '$lib/components/SpaceManagementDialog.svelte';
	import { getLibrary, refreshLibrary, processQueue } from '$lib/stores/library.svelte';
	import { getGarminStatus, refreshGarmin, transferUnsynced } from '$lib/stores/garmin.svelte';
	import { getProgress, setActive, initProgressListener } from '$lib/stores/progress.svelte';
	import { getTheme, toggleTheme } from '$lib/stores/theme.svelte';

	const library = getLibrary();
	const theme = getTheme();
	const garmin = getGarminStatus();
	const progress = getProgress();

	let syncing = $state(false);
	let transferring = $state(false);

	onMount(() => {
		let interval: ReturnType<typeof setInterval> | undefined;
		const unlisten = initProgressListener();

		(async () => {
			await Promise.all([refreshLibrary(), refreshGarmin()]);
			interval = setInterval(refreshGarmin, 5000);
		})();

		return () => {
			unlisten();
			if (interval) clearInterval(interval);
		};
	});

	async function handleSyncAll() {
		syncing = true;
		setActive(true);
		try {
			await processQueue();
			await refreshGarmin();
		} finally {
			syncing = false;
			setActive(false);
		}
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

	let unsyncedCount = $derived.by(() => {
		if (!garmin.data.connected) {
			return library.data.downloaded.filter((e) => e.synced_at === null).length;
		}
		const onWatch = new Set(garmin.data.episodes.map((e) => e.folder_name));
		return library.data.downloaded.filter((e) => !onWatch.has(e.folder_name)).length;
	});
</script>

<header class="toolbar">
	<h1>youtube-audio-chunker</h1>
	<div class="toolbar-actions">
		<button
			onclick={handleSyncAll}
			disabled={syncing || library.data.queue.length === 0}
		>
			{syncing ? 'Syncing...' : 'Sync All'}
		</button>
		<button
			onclick={handleTransfer}
			disabled={transferring || unsyncedCount === 0}
		>
			{transferring ? 'Transferring...' : `Transfer Unsynced (${unsyncedCount})`}
		</button>
		<a href="/settings" class="toolbar-icon">{'\u2699'}</a>
		<button class="theme-toggle" onclick={toggleTheme}>
			{theme.isDark ? '\u2600' : '\u263E'}
		</button>
	</div>
</header>

<GarminStatusStrip status={garmin.data} />

<main class="dashboard">
	<AddEpisodeForm />
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
</main>

<footer class="app-footer">
	Built by <a href="https://www.tonykwok.info/" target="_blank" rel="noopener">Tony Kwok</a>
</footer>

<ProgressPanel />
<SpaceManagementDialog />

<style>
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem max(1rem, calc((100% - 700px) / 2));
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
	.dashboard {
		display: flex;
		flex-direction: column;
		flex: 1;
		overflow: hidden;
		background: var(--color-bg-panel);
		align-items: center;
	}
	.dashboard > :global(*) {
		width: 100%;
		max-width: 700px;
	}
	.episode-scroll {
		flex: 1;
		overflow-y: auto;
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
