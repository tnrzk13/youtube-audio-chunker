<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import EpisodeEditForm from './EpisodeEditForm.svelte';
	import type { QueueEntry, ContentType } from '$lib/types';
	import { cancelAndRemove, editQueueEntry } from '$lib/stores/library.svelte';

	let { entries }: { entries: QueueEntry[] } = $props();

	let removingId = $state<string | null>(null);
	let editingId = $state<string | null>(null);
	let savingId = $state<string | null>(null);

	let editShowName = $state('');
	let editTitle = $state('');
	let editContentType = $state<ContentType>('music');

	function startEditing(entry: QueueEntry) {
		editingId = entry.video_id;
		editShowName = entry.show_name ?? '';
		editTitle = entry.title;
		editContentType = entry.content_type as ContentType;
	}

	function cancelEditing() {
		editingId = null;
	}

	async function handleSave(entry: QueueEntry) {
		savingId = entry.video_id;
		try {
			await editQueueEntry(entry.video_id, {
				show_name: editShowName || undefined,
				title: editTitle,
				content_type: editContentType,
			});
			editingId = null;
		} finally {
			savingId = null;
		}
	}

	async function handleRemove(videoId: string) {
		removingId = videoId;
		try {
			await cancelAndRemove(videoId);
		} finally {
			removingId = null;
		}
	}
</script>

{#each entries as entry (entry.video_id)}
		{#if editingId === entry.video_id}
			<EpisodeEditForm
				bind:title={editTitle}
				bind:showName={editShowName}
				bind:contentType={editContentType}
				saving={savingId !== null}
				onsave={() => handleSave(entry)}
				oncancel={cancelEditing}
			/>
		{:else}
			<EpisodeCard title={entry.title} contentType={entry.content_type} syncStatus="queued" statusTooltip="Processing">
				{#snippet actions()}
					<button
						class="btn-edit"
						onclick={() => startEditing(entry)}
						disabled={editingId !== null}
						title="Edit metadata"
					>
						&#9998;
					</button>
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
		{/if}
{/each}

