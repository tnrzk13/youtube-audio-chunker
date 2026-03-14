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

	function normalizeName(name: string): string {
		return name.replace(/[\/:*?"<>|＼／：＊？＂＜＞｜]/g, '').replace(/\s+/g, '-').replace(/-{2,}/g, '-').replace(/^-+|-+$/g, '');
	}

	function isOnWatch(ep: DownloadedEpisode): boolean {
		const normalized = normalizeName(ep.folder_name);
		return garmin.data.episodes.some((e) => normalizeName(e.folder_name) === normalized);
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
				{#if !isOnWatch(ep) && garmin.data.connected}
					<button
						class="btn-transfer"
						onclick={() => handleTransfer(ep.video_id)}
						disabled={transferringId !== null}
						title="Transfer to watch"
					>
						{transferringId === ep.video_id ? '...' : '\u2192'}
					</button>
				{:else if !isOnWatch(ep) && !garmin.data.connected && !ep.synced_at}
					<span class="connect-hint" title="Connect watch to sync">&#8987;</span>
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
	.btn-transfer {
		background: none;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-sm);
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		font-size: var(--font-size-sm);
		color: var(--color-primary);
		font-weight: 600;
		transition: all 0.15s;
	}
	.btn-transfer:hover:not(:disabled) {
		background: var(--color-primary-light);
	}
	.btn-transfer:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.connect-hint {
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		cursor: default;
		padding: 0.15rem 0.2rem;
	}
</style>
