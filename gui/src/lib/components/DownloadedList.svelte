<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import EpisodeEditForm from './EpisodeEditForm.svelte';
	import type { DownloadedEpisode, ContentType } from '$lib/types';
	import { removeEpisode, transferEpisode, editEpisode, resyncEpisode } from '$lib/stores/library.svelte';
	import { getGarminStatus, refreshGarmin } from '$lib/stores/garmin.svelte';
	import { setActive } from '$lib/stores/progress.svelte';

	let { episodes }: { episodes: DownloadedEpisode[] } = $props();

	let transferringId = $state<string | null>(null);
	let removingId = $state<string | null>(null);
	let editingId = $state<string | null>(null);
	let savingId = $state<string | null>(null);

	let editShowName = $state('');
	let editArtist = $state('');
	let editTitle = $state('');
	let editContentType = $state<ContentType>('music');

	const garmin = getGarminStatus();

	const STORAGE_KEY_SECTIONS = 'collapsed-sections';
	const STORAGE_KEY_GROUPS = 'collapsed-groups';

	let collapsedSections = $state<Set<string>>(
		new Set(JSON.parse(localStorage.getItem(STORAGE_KEY_SECTIONS) ?? '[]'))
	);
	let collapsedGroups = $state<Set<string>>(
		new Set(JSON.parse(localStorage.getItem(STORAGE_KEY_GROUPS) ?? '[]'))
	);

	function toggleSection(label: string) {
		if (collapsedSections.has(label)) {
			collapsedSections.delete(label);
		} else {
			collapsedSections.add(label);
		}
		collapsedSections = new Set(collapsedSections);
		localStorage.setItem(STORAGE_KEY_SECTIONS, JSON.stringify([...collapsedSections]));
	}

	function toggleGroup(showName: string) {
		if (collapsedGroups.has(showName)) {
			collapsedGroups.delete(showName);
		} else {
			collapsedGroups.add(showName);
		}
		collapsedGroups = new Set(collapsedGroups);
		localStorage.setItem(STORAGE_KEY_GROUPS, JSON.stringify([...collapsedGroups]));
	}

	const SECTION_ORDER = ['Podcasts', 'Music', 'Audiobooks'] as const;
	const SECTION_CONTENT_TYPE: Record<string, string> = {
		Podcasts: 'podcast',
		Music: 'music',
		Audiobooks: 'audiobook',
	};

	interface ShowGroup {
		showName: string;
		episodes: DownloadedEpisode[];
		totalSize: number;
	}

	interface Section {
		label: string;
		contentType: string;
		groups: ShowGroup[];
		ungrouped: DownloadedEpisode[];
	}

	let sections: Section[] = $derived(
		SECTION_ORDER
			.map((label) => {
				const ct = SECTION_CONTENT_TYPE[label];
				const items = episodes.filter((ep) => ep.content_type === ct);
				const withShow = items.filter((ep) => ep.show_name);
				const ungrouped = items.filter((ep) => !ep.show_name);

				const showMap = new Map<string, DownloadedEpisode[]>();
				for (const ep of withShow) {
					const list = showMap.get(ep.show_name!) ?? [];
					list.push(ep);
					showMap.set(ep.show_name!, list);
				}

				const groups: ShowGroup[] = [...showMap.entries()].map(
					([showName, eps]) => ({
						showName,
						episodes: eps,
						totalSize: eps.reduce((s, e) => s + e.total_size_bytes, 0),
					})
				);

				return { label, contentType: ct, groups, ungrouped };
			})
			.filter((s) => s.groups.length > 0 || s.ungrouped.length > 0)
	);

	function sectionEpisodeCount(section: Section): number {
		return section.groups.reduce((sum, g) => sum + g.episodes.length, 0) + section.ungrouped.length;
	}

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		return mb < 1 ? `${(bytes / 1000).toFixed(0)} KB` : `${mb.toFixed(1)} MB`;
	}

	function normalizeName(name: string): string {
		return name.replace(/[\/:*?"<>|＼／：＊？＂＜＞｜]/g, '').replace(/\s+/g, '-').replace(/-{2,}/g, '-').replace(/^-+|-+$/g, '');
	}

	function isOnWatch(ep: DownloadedEpisode): boolean {
		const normalized = normalizeName(ep.folder_name);
		return garmin.data.episodes.some((e) => normalizeName(e.folder_name) === normalized);
	}

	function subtitle(ep: DownloadedEpisode): string {
		const size = formatSize(ep.total_size_bytes);
		const chunks = ep.chunk_count === 1 ? '1 file' : `${ep.chunk_count} chunks`;
		return `${chunks} - ${size}`;
	}

	function startEditing(ep: DownloadedEpisode) {
		editingId = ep.video_id;
		editShowName = ep.show_name ?? '';
		editArtist = ep.artist ?? '';
		editTitle = ep.title;
		editContentType = ep.content_type as ContentType;
	}

	function cancelEditing() {
		editingId = null;
	}

	async function handleSave(ep: DownloadedEpisode) {
		savingId = ep.video_id;
		try {
			await editEpisode(ep.video_id, {
				show_name: editShowName || undefined,
				artist: editArtist || undefined,
				title: editTitle,
				content_type: editContentType,
			});

			if (isOnWatch(ep) && garmin.data.connected) {
				setActive(true);
				try {
					await resyncEpisode(ep.video_id);
					await refreshGarmin();
				} finally {
					setActive(false);
				}
			}

			editingId = null;
		} finally {
			savingId = null;
		}
	}

	async function handleRemove(videoId: string, title: string) {
		if (!confirm(`Delete ${title}? This episode will need to be re-downloaded.`)) return;
		removingId = videoId;
		try {
			await removeEpisode(videoId);
		} finally {
			removingId = null;
		}
	}

	async function handleTransfer(videoId: string) {
		transferringId = videoId;
		setActive(true);
		try {
			await transferEpisode(videoId);
			await refreshGarmin();
		} finally {
			transferringId = null;
			setActive(false);
		}
	}
</script>

{#snippet episodeRow(ep: DownloadedEpisode)}
	{#if editingId === ep.video_id}
		<EpisodeEditForm
			bind:title={editTitle}
			bind:showName={editShowName}
			bind:artist={editArtist}
			bind:contentType={editContentType}
			showArtist={true}
			saving={savingId !== null}
			onsave={() => handleSave(ep)}
			oncancel={cancelEditing}
		/>
	{:else}
		<EpisodeCard
		title={ep.title}
		contentType={ep.content_type}
		subtitle={subtitle(ep)}
		syncStatus={isOnWatch(ep) ? 'synced' : undefined}
		statusTooltip={isOnWatch(ep) ? 'On watch' : undefined}
	>
			{#snippet actions()}
				<button
					class="btn-edit"
					onclick={() => startEditing(ep)}
					disabled={editingId !== null}
					title="Edit metadata"
				>
					&#9998;
				</button>
				{#if !isOnWatch(ep) && garmin.data.connected}
					<button
						class="btn-transfer"
						onclick={() => handleTransfer(ep.video_id)}
						disabled={transferringId !== null}
						title="Transfer to watch"
					>
						{transferringId === ep.video_id ? '...' : '\u2192'}
					</button>
				{:else if !isOnWatch(ep) && !garmin.data.connected && !ep.synced_at}
					<span class="connect-hint" title="Connect watch to sync">&#8987;</span>
				{/if}
				<button
					class="btn-icon"
					onclick={() => handleRemove(ep.video_id, ep.title)}
					disabled={removingId !== null}
					title="Delete episode"
				>
					{removingId === ep.video_id ? '...' : '✕'}
				</button>
			{/snippet}
		</EpisodeCard>
	{/if}
{/snippet}

{#if episodes.length === 0}
	<p class="empty">No downloaded episodes</p>
{:else}
	{#each sections as section (section.label)}
		<button class="section-header" onclick={() => toggleSection(section.label)}>
			<span class="chevron" class:collapsed={collapsedSections.has(section.label)}>{'\u25BE'}</span>
			{section.label}
			<span class="section-count">{sectionEpisodeCount(section)}</span>
		</button>

		{#if !collapsedSections.has(section.label)}
			{#each section.groups as group (group.showName)}
				<div class="show-group">
					<button class="show-header" onclick={() => toggleGroup(group.showName)}>
						<span class="chevron" class:collapsed={collapsedGroups.has(group.showName)}>{'\u25BE'}</span>
						{group.showName}
						<span class="show-meta">
							{group.episodes.length} {group.episodes.length === 1 ? 'episode' : 'episodes'}
							- {formatSize(group.totalSize)}
						</span>
					</button>
					{#if !collapsedGroups.has(group.showName)}
						{#each group.episodes as ep (ep.video_id)}
							{@render episodeRow(ep)}
						{/each}
					{/if}
				</div>
			{/each}

			{#each section.ungrouped as ep (ep.video_id)}
				{@render episodeRow(ep)}
			{/each}
		{/if}
	{/each}
{/if}

<style>
	.section-header {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		width: 100%;
		background: none;
		border: none;
		border-top: 1px solid var(--color-border-subtle);
		font-size: var(--font-size-xs);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-hint);
		padding: 0.5rem 0.75rem 0.2rem;
		cursor: pointer;
		text-align: left;
	}
	.section-header:first-child {
		border-top: none;
	}
	.section-header:hover {
		color: var(--color-text-secondary);
	}
	.section-count {
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.show-group {
		margin: 0.5rem 0.5rem 0.5rem 0.75rem;
		border-left: 3px solid var(--color-border-light);
		border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
		background: var(--color-bg-hover);
	}
	.show-header {
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		width: 100%;
		background: none;
		border: none;
		font-size: var(--font-size-sm);
		font-weight: 600;
		color: var(--color-text);
		padding: 0.45rem 0.75rem 0.15rem;
		cursor: pointer;
		text-align: left;
	}
	.show-header:hover {
		color: var(--color-primary);
	}
	.chevron {
		display: inline-block;
		transition: transform 0.15s;
		font-size: var(--font-size-xs);
	}
	.chevron.collapsed {
		transform: rotate(-90deg);
	}
	.show-meta {
		font-weight: 400;
		font-size: var(--font-size-xs);
		color: var(--color-text-hint);
	}
	.btn-transfer {
		background: none;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-sm);
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		font-size: var(--font-size-sm);
		color: var(--color-primary);
		font-weight: 600;
		transition: all 0.15s;
	}
	.btn-transfer:hover:not(:disabled) {
		background: var(--color-primary-light);
	}
	.btn-transfer:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.connect-hint {
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		cursor: default;
		padding: 0.15rem 0.2rem;
	}
</style>
