<script lang="ts">
	import { onMount } from 'svelte';
	import AddEpisodeForm from '$lib/components/AddEpisodeForm.svelte';
	import QueueList from '$lib/components/QueueList.svelte';
	import DownloadedList from '$lib/components/DownloadedList.svelte';
	import WatchEpisodeList from '$lib/components/WatchEpisodeList.svelte';
	import StorageBar from '$lib/components/StorageBar.svelte';
	import ProgressPanel from '$lib/components/ProgressPanel.svelte';
	import { getLibrary, refreshLibrary, processQueue } from '$lib/stores/library';
	import { getGarminStatus, refreshGarmin, transferUnsynced } from '$lib/stores/garmin';
	import { getProgress, setActive, initProgressListener } from '$lib/stores/progress';

	const library = getLibrary();
	const garmin = getGarminStatus();
	const progress = getProgress();

	let syncing = $state(false);
	let transferring = $state(false);

	onMount(async () => {
		await Promise.all([refreshLibrary(), refreshGarmin()]);
		const unlisten = await initProgressListener();

		// Poll garmin status every 5 seconds
		const interval = setInterval(refreshGarmin, 5000);

		return () => {
			unlisten();
			clearInterval(interval);
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
	<a href="/settings" class="settings-link">Settings</a>
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

	<section class="column">
		<div class="column-header">
			<h2>Local ({library.data.downloaded.length})</h2>
		</div>
		<div class="column-scroll">
			<DownloadedList episodes={library.data.downloaded} />
		</div>
	</section>

	<section class="column">
		<div class="column-header">
			<h2>Watch</h2>
			<span class="status-dot" class:connected={garmin.data.connected}></span>
		</div>
		<StorageBar status={garmin.data} />
		<div class="column-scroll">
			<WatchEpisodeList episodes={garmin.data.episodes} />
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

<style>
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid #ddd;
		background: #fff;
		flex-shrink: 0;
	}
	h1 {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}
	.settings-link {
		font-size: 0.8rem;
		color: #1976d2;
		text-decoration: none;
	}
	.settings-link:hover {
		text-decoration: underline;
	}
	.dashboard {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 0;
		flex: 1;
		overflow: hidden;
	}
	.column {
		display: flex;
		flex-direction: column;
		border-right: 1px solid #ddd;
		background: #fff;
		overflow: hidden;
	}
	.column:last-child {
		border-right: none;
	}
	.column-header {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid #eee;
		flex-shrink: 0;
	}
	.column-header h2 {
		font-size: 0.85rem;
		font-weight: 600;
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #555;
	}
	.column-scroll {
		flex: 1;
		overflow-y: auto;
	}
	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #ccc;
	}
	.status-dot.connected {
		background: #43a047;
	}
	.actions-bar {
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		border-top: 1px solid #ddd;
		background: #fff;
		flex-shrink: 0;
	}
	.actions-bar button {
		font-size: 0.8rem;
		padding: 0.4rem 1rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: #fff;
		cursor: pointer;
	}
	.actions-bar button:hover:not(:disabled) {
		background: #f5f5f5;
	}
	.actions-bar button:disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
