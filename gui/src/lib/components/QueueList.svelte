<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import EpisodeEditForm from './EpisodeEditForm.svelte';
	import type { QueueEntry, ContentType } from '$lib/types';
	import { cancelAndRemove, cancelAndRemoveMultiple, editQueueEntry } from '$lib/stores/library.svelte';

	let { entries }: { entries: QueueEntry[] } = $props();

	let removingId = $state<string | null>(null);
	let editingId = $state<string | null>(null);
	let savingId = $state<string | null>(null);

	let selectMode = $state(false);
	let selectedIds = $state<Set<string>>(new Set());
	let batchRemoving = $state(false);

	let editShowName = $state('');
	let editTitle = $state('');
	let editContentType = $state<ContentType>('music');

	function enterSelectMode() {
		editingId = null;
		selectMode = true;
		selectedIds = new Set();
	}

	function exitSelectMode() {
		selectMode = false;
		selectedIds = new Set();
	}

	function toggleSelected(videoId: string) {
		if (selectedIds.has(videoId)) {
			selectedIds.delete(videoId);
		} else {
			selectedIds.add(videoId);
		}
		selectedIds = new Set(selectedIds);
	}

	async function handleBatchRemove() {
		if (selectedIds.size === 0) return;
		batchRemoving = true;
		const ids = [...selectedIds];
		exitSelectMode();
		try {
			await cancelAndRemoveMultiple(ids);
		} finally {
			batchRemoving = false;
		}
	}

	function startEditing(entry: QueueEntry) {
		editingId = entry.video_id;
		editShowName = entry.show_name ?? '';
		editTitle = entry.title;
		editContentType = entry.content_type;
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

{#if entries.length > 0}
	{#if selectMode}
		<div class="select-bar">
			<button class="btn btn-danger" onclick={handleBatchRemove} disabled={selectedIds.size === 0 || batchRemoving}>
				{batchRemoving ? 'Removing...' : `Remove (${selectedIds.size})`}
			</button>
			<button class="btn btn-outline" onclick={exitSelectMode} disabled={batchRemoving}>Cancel</button>
		</div>
	{:else}
		<div class="select-toggle">
			<button class="btn btn-outline" onclick={enterSelectMode}>Select</button>
		</div>
	{/if}
{/if}

{#each entries as entry (entry.video_id)}
	{#if selectMode}
		<EpisodeCard
			title={entry.title}
			contentType={entry.content_type}
			selectable={true}
			selected={selectedIds.has(entry.video_id)}
			onToggle={() => toggleSelected(entry.video_id)}
		/>
	{:else if editingId === entry.video_id}
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


