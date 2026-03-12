<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { QueueEntry } from '$lib/types';
	import { cancelAndRemove } from '$lib/stores/library.svelte';

	let { entries }: { entries: QueueEntry[] } = $props();

	let removingId = $state<string | null>(null);

	async function handleRemove(videoId: string) {
		removingId = videoId;
		try {
			await cancelAndRemove(videoId);
		} finally {
			removingId = null;
		}
	}
</script>

{#if entries.length === 0}
	<p class="empty">No episodes queued</p>
{:else}
	{#each entries as entry (entry.video_id)}
		<EpisodeCard title={entry.title} contentType={entry.content_type}>
			{#snippet actions()}
				<button
					class="btn-icon"
					onclick={() => handleRemove(entry.video_id)}
					disabled={removingId !== null}
					title="Cancel and remove"
				>
					{removingId === entry.video_id ? '...' : '✕'}
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
</style>
