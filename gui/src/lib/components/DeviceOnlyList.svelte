<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import type { DownloadedEpisode, GarminEpisode } from '$lib/types';
	import { removeFromGarmin, removeFromGarminBatch } from '$lib/stores/garmin.svelte';

	let {
		garminEpisodes,
		downloadedEpisodes,
	}: {
		garminEpisodes: GarminEpisode[];
		downloadedEpisodes: DownloadedEpisode[];
	} = $props();

	let removingId = $state<string | null>(null);
	let errorMsg = $state('');

	let selectMode = $state(false);
	let selectedNames = $state<Set<string>>(new Set());
	let batchRemoving = $state(false);

	function enterSelectMode() {
		selectMode = true;
		selectedNames = new Set();
	}

	function exitSelectMode() {
		selectMode = false;
		selectedNames = new Set();
	}

	function toggleSelected(folderName: string) {
		if (selectedNames.has(folderName)) {
			selectedNames.delete(folderName);
		} else {
			selectedNames.add(folderName);
		}
		selectedNames = new Set(selectedNames);
	}

	async function handleBatchRemove() {
		if (selectedNames.size === 0) return;
		errorMsg = '';
		batchRemoving = true;
		const names = [...selectedNames];
		exitSelectMode();
		try {
			const result = await removeFromGarminBatch(names);
			if (result.failed.length > 0) {
				errorMsg = `Failed to remove ${result.failed.length} episode(s): ${result.failed.map((f) => f.folder_name).join(', ')}`;
			}
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			batchRemoving = false;
		}
	}

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
	{#if selectMode}
		<div class="select-bar">
			<label class="select-all">
				<input
					type="checkbox"
					checked={selectedNames.size === deviceOnlyEpisodes.length && deviceOnlyEpisodes.length > 0}
					indeterminate={selectedNames.size > 0 && selectedNames.size < deviceOnlyEpisodes.length}
					onchange={() => {
						if (selectedNames.size === deviceOnlyEpisodes.length) {
							selectedNames = new Set();
						} else {
							selectedNames = new Set(deviceOnlyEpisodes.map(ep => ep.folder_name));
						}
					}}
				/>
				All
			</label>
			<button class="btn btn-danger" onclick={handleBatchRemove} disabled={selectedNames.size === 0 || batchRemoving}>
				{batchRemoving ? 'Removing...' : `Remove (${selectedNames.size})`}
			</button>
			<button class="btn btn-outline" onclick={exitSelectMode} disabled={batchRemoving}>Cancel</button>
		</div>
	{:else}
		<div class="select-toggle">
			<button class="btn btn-outline" onclick={enterSelectMode}>Select</button>
		</div>
	{/if}
	{#each deviceOnlyEpisodes as ep (ep.folder_name)}
		{#if selectMode}
			<EpisodeCard
				title={ep.folder_name}
				contentType={ep.location === 'Podcasts' ? 'podcast' : ep.location === 'Audiobooks' ? 'audiobook' : 'music'}
				subtitle={formatSize(ep.total_size_bytes)}
				selectable={true}
				selected={selectedNames.has(ep.folder_name)}
				onToggle={() => toggleSelected(ep.folder_name)}
			/>
		{:else}
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
		{/if}
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
