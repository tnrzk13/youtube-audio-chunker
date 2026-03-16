<script lang="ts">
	import type { ContentType } from '$lib/types';

	let {
		title = $bindable(),
		showName = $bindable(),
		artist = $bindable(''),
		contentType = $bindable(),
		showArtist = false,
		saving,
		onsave,
		oncancel,
	}: {
		title: string;
		showName: string;
		artist?: string;
		contentType: ContentType;
		showArtist?: boolean;
		saving: boolean;
		onsave: () => void;
		oncancel: () => void;
	} = $props();
</script>

<div class="edit-card">
	<label class="edit-field">
		<span class="edit-label">Title</span>
		<input type="text" bind:value={title} placeholder="Title" />
	</label>
	<label class="edit-field">
		<span class="edit-label">Show</span>
		<input type="text" bind:value={showName} placeholder="Show name" />
	</label>
	{#if showArtist}
		<label class="edit-field">
			<span class="edit-label">Artist</span>
			<input type="text" bind:value={artist} placeholder="Artist" />
		</label>
	{/if}
	<label class="edit-field">
		<span class="edit-label">Type</span>
		<select bind:value={contentType}>
			<option value="music">Music</option>
			<option value="podcast">Podcast</option>
			<option value="audiobook">Audiobook</option>
		</select>
	</label>
	<div class="edit-actions">
		<button
			class="btn btn-sm btn-primary"
			onclick={onsave}
			disabled={saving || !title.trim()}
		>
			{saving ? 'Saving...' : 'Save'}
		</button>
		<button class="btn btn-sm btn-outline" onclick={oncancel} disabled={saving}>
			Cancel
		</button>
	</div>
</div>

<style>
	.edit-card {
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		background: var(--color-bg-hover);
	}
	.edit-field {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.edit-label {
		font-size: var(--font-size-sm);
		color: var(--color-text-hint);
		min-width: 3rem;
	}
	.edit-card input,
	.edit-card select {
		flex: 1;
		font-family: inherit;
		font-size: var(--font-size-md);
		padding: 0.25rem 0.4rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-bg-panel);
		transition: border-color 0.15s;
	}
	.edit-card input:focus,
	.edit-card select:focus {
		outline: none;
		border-color: var(--color-primary);
	}
	.edit-actions {
		display: flex;
		gap: 0.4rem;
		justify-content: flex-end;
		margin-top: 0.1rem;
	}
</style>
