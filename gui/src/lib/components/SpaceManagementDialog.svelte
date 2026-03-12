<script lang="ts">
	import { listen } from '@tauri-apps/api/event';
	import { onMount } from 'svelte';
	import type { GarminEpisode } from '$lib/types';

	let open = $state(false);
	let episodes = $state<GarminEpisode[]>([]);
	let deficitBytes = $state(0);

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		return mb < 1 ? `${(bytes / 1000).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
	}

	onMount(async () => {
		const unlisten = await listen<{ episodes: GarminEpisode[]; deficit_bytes: number }>(
			'sidecar:reverse:confirm_removal',
			(event) => {
				episodes = event.payload.episodes;
				deficitBytes = event.payload.deficit_bytes;
				open = true;
			}
		);
		return unlisten;
	});

	function handleConfirm() {
		open = false;
	}

	function handleCancel() {
		open = false;
	}
</script>

{#if open}
	<div class="overlay">
		<div class="dialog">
			<h3>Free space on watch?</h3>
			<p>Need to free {formatSize(deficitBytes)} to transfer. These episodes would be removed:</p>
			<ul>
				{#each episodes as ep}
					<li>{ep.folder_name} ({formatSize(ep.total_size_bytes)})</li>
				{/each}
			</ul>
			<div class="dialog-actions">
				<button class="btn-cancel" onclick={handleCancel}>Cancel</button>
				<button class="btn-confirm" onclick={handleConfirm}>Remove & Transfer</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 900;
	}
	.dialog {
		background: #fff;
		border-radius: 8px;
		padding: 1.5rem;
		width: min(90%, 420px);
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
	}
	h3 {
		margin: 0 0 0.5rem;
		font-size: 1rem;
	}
	p {
		font-size: 0.85rem;
		color: #555;
		margin: 0 0 0.75rem;
	}
	ul {
		margin: 0 0 1rem;
		padding-left: 1.2rem;
		font-size: 0.85rem;
	}
	li {
		margin-bottom: 0.3rem;
	}
	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
	.btn-cancel {
		padding: 0.4rem 1rem;
		border: 1px solid #ddd;
		border-radius: 6px;
		background: #fff;
		cursor: pointer;
		font-size: 0.8rem;
		transition: all 0.15s;
	}
	.btn-cancel:hover {
		background: #f5f5f5;
	}
	.btn-confirm {
		padding: 0.4rem 1rem;
		border: 1px solid #d32f2f;
		border-radius: 6px;
		background: #d32f2f;
		color: #fff;
		cursor: pointer;
		font-size: 0.8rem;
		transition: all 0.15s;
	}
	.btn-confirm:hover {
		background: #c62828;
	}
</style>
