<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { GarminEpisode } from '$lib/types';
	import { removeFromGarmin } from '$lib/stores/garmin';

	let { episodes }: { episodes: GarminEpisode[] } = $props();

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		return mb < 1 ? `${(bytes / 1000).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
	}

	async function handleRemove(folderName: string) {
		await removeFromGarmin(folderName);
	}
</script>

{#if episodes.length === 0}
	<p class="empty">No episodes on watch</p>
{:else}
	{#each episodes as ep (ep.folder_name)}
		<EpisodeCard
			title={ep.folder_name}
			contentType={ep.location === 'Podcasts' ? 'podcast' : ep.location === 'Audiobooks' ? 'audiobook' : 'music'}
			subtitle="{formatSize(ep.total_size_bytes)} - {ep.location}"
		>
			{#snippet actions()}
				<button class="btn-icon" onclick={() => handleRemove(ep.folder_name)} title="Remove from watch">✕</button>
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
