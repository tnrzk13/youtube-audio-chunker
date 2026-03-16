<script lang="ts">
	import { call } from '$lib/backend';
	import { onMount } from 'svelte';
	import type { GarminEpisode } from '$lib/types';

	let open = $state(false);
	let episodes = $state<GarminEpisode[]>([]);
	let deficitBytes = $state(0);
	let requestId = $state<unknown>(null);

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		return mb < 1 ? `${(bytes / 1000).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
	}

	onMount(() => {
		// Reverse requests only work in Tauri mode (sidecar stdio bidirectional flow)
		if (!(window as any).__TAURI_INTERNALS__) return;

		let unlisten: (() => void) | undefined;
		import('@tauri-apps/api/event').then(({ listen }) => {
			listen<{ episodes: GarminEpisode[]; deficit_bytes: number; _request_id: unknown }>(
				'sidecar:reverse:confirm_removal',
				(event) => {
					episodes = event.payload.episodes;
					deficitBytes = event.payload.deficit_bytes;
					requestId = event.payload._request_id;
					open = true;
				}
			).then((fn) => { unlisten = fn; });
		});

		return () => unlisten?.();
	});

	function handleConfirm() {
		open = false;
		call('respond_to_reverse_request', { requestId, result: true });
	}

	function handleCancel() {
		open = false;
		call('respond_to_reverse_request', { requestId, result: false });
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
				<button class="btn btn-outline" onclick={handleCancel}>Cancel</button>
				<button class="btn btn-danger" onclick={handleConfirm}>Remove & Transfer</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: var(--color-overlay);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 900;
		animation: fadeIn 0.15s ease-out;
	}
	.dialog {
		background: var(--color-bg-panel);
		border-radius: var(--radius-lg);
		padding: 1.5rem;
		width: min(90%, 420px);
		box-shadow: var(--shadow-dialog);
		animation: scaleUp 0.2s ease-out;
	}
	@keyframes fadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	@keyframes scaleUp {
		from { transform: scale(0.95); opacity: 0; }
		to { transform: scale(1); opacity: 1; }
	}
	h3 {
		margin: 0 0 0.5rem;
		font-size: var(--font-size-lg);
	}
	p {
		font-size: var(--font-size-base);
		color: var(--color-text-secondary);
		margin: 0 0 0.75rem;
	}
	ul {
		margin: 0 0 1rem;
		padding-left: 1.2rem;
		font-size: var(--font-size-base);
	}
	li {
		margin-bottom: 0.3rem;
	}
	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
