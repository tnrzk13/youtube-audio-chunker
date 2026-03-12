<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { DownloadedEpisode } from '$lib/types';
	import { removeEpisode } from '$lib/stores/library.svelte';

	let { episodes }: { episodes: DownloadedEpisode[] } = $props();

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

	async function handleRemove(videoId: string) {
		await removeEpisode(videoId);
	}
</script>

{#if episodes.length === 0}
	<p class="empty">No downloaded episodes</p>
{:else}
	{#each episodes as ep (ep.video_id)}
		<EpisodeCard title={ep.title} contentType={ep.content_type} subtitle={subtitle(ep)}>
			{#snippet actions()}
				<button class="btn-icon" onclick={() => handleRemove(ep.video_id)} title="Delete episode">✕</button>
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
	.btn-icon:hover {
		background: #fee;
		color: #c00;
		border-color: #c00;
	}
</style>
