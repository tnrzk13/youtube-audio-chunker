<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { DownloadedEpisode } from '$lib/types';
	import { removeEpisode, transferEpisode } from '$lib/stores/library.svelte';
	import { getGarminStatus, refreshGarmin } from '$lib/stores/garmin.svelte';
	import { setActive } from '$lib/stores/progress.svelte';

	let { episodes }: { episodes: DownloadedEpisode[] } = $props();

	let transferringId = $state<string | null>(null);
	let removingId = $state<string | null>(null);
	const garmin = getGarminStatus();

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		return mb < 1 ? `${(bytes / 1000).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
	}

	function subtitle(ep: DownloadedEpisode): string {
		const size = formatSize(ep.total_size_bytes);
		const chunks = ep.chunk_count === 1 ? '1 file' : `${ep.chunk_count} chunks`;
		const sync = ep.synced_at ? 'synced' : 'unsynced';
		return `${chunks} - ${size} - ${sync}`;
	}

	async function handleRemove(videoId: string, title: string) {
		if (!confirm(`Delete ${title}? This episode will need to be re-downloaded.`)) return;
		removingId = videoId;
		try {
			await removeEpisode(videoId);
		} finally {
			removingId = null;
		}
	}

	async function handleTransfer(videoId: string) {
		transferringId = videoId;
		setActive(true);
		try {
			await transferEpisode(videoId);
			await refreshGarmin();
		} finally {
			transferringId = null;
			setActive(false);
		}
	}
</script>

{#if episodes.length === 0}
	<p class="empty">No downloaded episodes</p>
{:else}
	{#each episodes as ep (ep.video_id)}
		<EpisodeCard title={ep.title} contentType={ep.content_type} subtitle={subtitle(ep)}>
			{#snippet actions()}
				{#if !ep.synced_at && garmin.data.connected}
					<button
						class="btn-transfer"
						onclick={() => handleTransfer(ep.video_id)}
						disabled={transferringId !== null}
						title="Transfer to watch"
					>
						{transferringId === ep.video_id ? '...' : '\u2192'}
					</button>
				{/if}
				<button
					class="btn-icon"
					onclick={() => handleRemove(ep.video_id, ep.title)}
					disabled={removingId !== null}
					title="Delete episode"
				>
					{removingId === ep.video_id ? '...' : '✕'}
				</button>
			{/snippet}
		</EpisodeCard>
	{/each}
{/if}

<style>
	.empty {
		padding: 1rem;
		color: #999;
		font-size: 0.85rem;
		text-align: center;
	}
	.btn-icon {
		background: none;
		border: 1px solid #ddd;
		border-radius: 3px;
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		font-size: 0.75rem;
		color: #999;
	}
	.btn-icon:hover:not(:disabled) {
		background: #fee;
		color: #c00;
		border-color: #c00;
	}
	.btn-icon:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.btn-transfer {
		background: none;
		border: 1px solid #1976d2;
		border-radius: 3px;
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		font-size: 0.75rem;
		color: #1976d2;
		font-weight: 600;
	}
	.btn-transfer:hover:not(:disabled) {
		background: #e3f2fd;
	}
	.btn-transfer:disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
