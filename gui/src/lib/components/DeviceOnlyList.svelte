<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { DownloadedEpisode, GarminEpisode } from '$lib/types';
	import { removeFromGarmin } from '$lib/stores/garmin.svelte';

	let {
		garminEpisodes,
		downloadedEpisodes,
	}: {
		garminEpisodes: GarminEpisode[];
		downloadedEpisodes: DownloadedEpisode[];
	} = $props();

	let removingId = $state<string | null>(null);
	let errorMsg = $state('');

	function normalizeName(name: string): string {
		return name
			.replace(/[\/:*?"<>|＼／：＊？＂＜＞｜]/g, '')
			.replace(/\s+/g, '-')
			.replace(/-{2,}/g, '-')
			.replace(/^-+|-+$/g, '');
	}

	let deviceOnlyEpisodes = $derived.by(() => {
		const localNames = new Set(downloadedEpisodes.map((ep) => normalizeName(ep.folder_name)));
		return garminEpisodes.filter((ep) => !localNames.has(normalizeName(ep.folder_name)));
	});

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

{#if deviceOnlyEpisodes.length > 0}
	<div class="section-header">Device Only</div>
	{#if errorMsg}
		<div class="error">{errorMsg}</div>
	{/if}
	{#each deviceOnlyEpisodes as ep (ep.folder_name)}
		<EpisodeCard
			title={ep.folder_name}
			contentType={ep.location === 'Podcasts' ? 'podcast' : ep.location === 'Audiobooks' ? 'audiobook' : 'music'}
			subtitle={formatSize(ep.total_size_bytes)}
			syncStatus="synced"
			statusTooltip="On watch (not in library)"
		>
			{#snippet actions()}
				<button
					class="btn-icon"
					onclick={() => handleRemove(ep.folder_name)}
					disabled={removingId !== null}
					title="Remove from watch"
				>
					{removingId === ep.folder_name ? '...' : '\u2715'}
				</button>
			{/snippet}
		</EpisodeCard>
	{/each}
{/if}

<style>
	.section-header {
		font-size: var(--font-size-xs);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-hint);
		padding: 0.5rem 0.75rem 0.2rem;
		border-top: 1px solid var(--color-border-subtle);
	}
	.error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		padding: 0.4rem 0.75rem;
		background: var(--color-danger-bg);
		border-bottom: 1px solid var(--color-danger-border);
	}
</style>
