<script lang="ts">
	import { onMount } from 'svelte';
	import AddEpisodeForm from '$lib/components/AddEpisodeForm.svelte';
	import QueueList from '$lib/components/QueueList.svelte';
	import DownloadedList from '$lib/components/DownloadedList.svelte';
	import WatchEpisodeList from '$lib/components/WatchEpisodeList.svelte';
	import StorageBar from '$lib/components/StorageBar.svelte';
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
		let unlisten: (() => void) | undefined;
		let interval: ReturnType<typeof setInterval> | undefined;

		(async () => {
			await Promise.all([refreshLibrary(), refreshGarmin()]);
			unlisten = await initProgressListener();
			interval = setInterval(refreshGarmin, 5000);
		})();

		return () => {
			unlisten?.();
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

	let unsyncedCount = $derived(
		library.data.downloaded.filter((e) => e.synced_at === null).length
	);
</script>

<header class="toolbar">
	<h1>youtube-audio-chunker</h1>
	<div class="toolbar-actions">
		<a href="/settings" class="settings-link">Settings</a>
		<button class="theme-toggle" onclick={toggleTheme}>
			{theme.isDark ? '\u2600' : '\u263E'}
		</button>
	</div>
</header>

<main class="dashboard">
	<section class="column">
		<div class="column-header">
			<h2>Queue ({library.data.queue.length})</h2>
		</div>
		<AddEpisodeForm />
		<div class="column-scroll">
			<QueueList entries={library.data.queue} />
		</div>
	</section>

	<span class="flow-arrow">{'\u2192'}</span>

	<section class="column">
		<div class="column-header">
			<h2>Local ({library.data.downloaded.length})</h2>
		</div>
		<div class="column-scroll">
			<DownloadedList episodes={library.data.downloaded} />
		</div>
	</section>

	<span class="flow-arrow">{'\u2192'}</span>

	<section class="column">
		<div class="column-header">
			<h2>Watch</h2>
			<span class="status-dot" class:connected={garmin.data.connected}></span>
		</div>
		<StorageBar status={garmin.data} />
		<div class="column-scroll">
			<WatchEpisodeList episodes={garmin.data.episodes} connected={garmin.data.connected} />
		</div>
	</section>
</main>

<footer class="actions-bar">
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
</footer>

<ProgressPanel />
<SpaceManagementDialog />

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
	.toolbar-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.settings-link {
		font-size: var(--font-size-md);
		color: var(--color-primary);
		text-decoration: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-sm);
		padding: 0.15rem 0.5rem;
		transition: all 0.15s;
	}
	.settings-link:hover {
		background: var(--color-bg-hover);
	}
	.dashboard {
		display: grid;
		grid-template-columns: 1fr auto 1fr auto 1fr;
		gap: 0;
		flex: 1;
		overflow: hidden;
	}
	.flow-arrow {
		display: flex;
		align-items: center;
		color: var(--color-border-light);
		font-size: var(--font-size-lg);
		padding: 0 0.15rem;
		user-select: none;
	}
	.column {
		display: flex;
		flex-direction: column;
		box-shadow: var(--shadow-column);
		background: var(--color-bg-panel);
		overflow: hidden;
	}
	.column:last-child {
		box-shadow: none;
	}
	.column-header {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		background: var(--color-bg-page);
		flex-shrink: 0;
	}
	.column-header h2 {
		font-size: var(--font-size-base);
		font-weight: 600;
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-secondary);
	}
	.column-scroll {
		flex: 1;
		overflow-y: auto;
	}
	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: var(--radius-full);
		background: var(--color-border-light);
		transition: background 0.15s;
	}
	.status-dot.connected {
		background: var(--color-success);
	}
	.actions-bar {
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		box-shadow: var(--shadow-footer);
		background: var(--color-bg-footer);
		flex-shrink: 0;
		z-index: 1;
	}
	.actions-bar button {
		font-size: var(--font-size-md);
		padding: 0.4rem 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-panel);
		cursor: pointer;
		transition: all 0.15s;
	}
	.actions-bar button:hover:not(:disabled) {
		background: var(--color-bg-button-hover);
	}
	.actions-bar button:disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
