<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { GarminEpisode } from '$lib/types';
	import { removeFromGarmin } from '$lib/stores/garmin.svelte';

	let { episodes, connected }: { episodes: GarminEpisode[]; connected: boolean } = $props();

	let errorMsg = $state('');
	let removingId = $state<string | null>(null);

	const SECTION_ORDER = ['Podcasts', 'Music', 'Audiobooks'] as const;
	const SECTION_CONTENT_TYPE: Record<string, string> = {
		Music: 'music',
		Podcasts: 'podcast',
		Audiobooks: 'audiobook',
	};

	let groupedEpisodes = $derived(
		SECTION_ORDER
			.map((location) => ({
				location,
				contentType: SECTION_CONTENT_TYPE[location],
				items: episodes.filter((ep) => ep.location === location),
			}))
			.filter((group) => group.items.length > 0)
	);

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		return mb < 1 ? `${(bytes / 1000).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
	}

	async function handleRemove(folderName: string) {
		errorMsg = '';
		removingId = folderName;
		try {
			await removeFromGarmin(folderName);
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			removingId = null;
		}
	}
</script>

{#if errorMsg}
	<div class="error">{errorMsg}</div>
{/if}
{#if !connected}
	<p class="empty disconnected">Connect your Garmin watch</p>
{:else if episodes.length === 0}
	<p class="empty">No episodes on watch</p>
{:else}
	{#each groupedEpisodes as group (group.location)}
		<div class="section-header">{group.location}</div>
		{#each group.items as ep (ep.folder_name)}
			<EpisodeCard
				title={ep.folder_name}
				contentType={group.contentType}
				subtitle={formatSize(ep.total_size_bytes)}
			>
				{#snippet actions()}
					<button
						class="btn-icon"
						onclick={() => handleRemove(ep.folder_name)}
						disabled={removingId !== null}
						title="Remove from watch"
					>
						{removingId === ep.folder_name ? '...' : '✕'}
					</button>
				{/snippet}
			</EpisodeCard>
		{/each}
	{/each}
{/if}

<style>
	.empty {
		padding: 1rem;
		color: #999;
		font-size: 0.85rem;
		text-align: center;
	}
	.disconnected {
		color: #bbb;
	}
	.section-header {
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #888;
		padding: 0.5rem 0.75rem 0.2rem;
		border-top: 1px solid #eee;
	}
	.section-header:first-child {
		border-top: none;
	}
	.btn-icon {
		background: none;
		border: 1px solid #ddd;
		border-radius: 4px;
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		font-size: 0.75rem;
		color: #999;
		transition: all 0.15s;
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
	.error {
		font-size: 0.75rem;
		color: #c00;
		padding: 0.4rem 0.75rem;
		background: #fee;
		border-bottom: 1px solid #fcc;
	}
</style>
