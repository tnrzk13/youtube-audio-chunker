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
</style>
