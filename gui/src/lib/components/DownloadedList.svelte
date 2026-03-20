<script lang="ts">
	import EpisodeCard from './EpisodeCard.svelte';
	import EpisodeEditForm from './EpisodeEditForm.svelte';
	import type { DownloadedEpisode, ContentType } from '$lib/types';
	import { formatDuration } from '$lib/format';
	import { STORAGE_KEYS } from '$lib/constants';
	import { removeEpisode, removeEpisodes, transferEpisode, editEpisode, resyncEpisode } from '$lib/stores/library.svelte';
	import { getGarminStatus, refreshGarmin } from '$lib/stores/garmin.svelte';
	import { setActive } from '$lib/stores/progress.svelte';

	let { episodes }: { episodes: DownloadedEpisode[] } = $props();

	let transferringId = $state<string | null>(null);
	let editingId = $state<string | null>(null);
	let savingId = $state<string | null>(null);

	const UNDO_DELAY_MS = 5000;
	let pendingDelete = $state<{ videoId: string; title: string; timeoutId: ReturnType<typeof setTimeout> } | null>(null);

	let selectMode = $state(false);
	let selectedIds = $state<Set<string>>(new Set());
	let pendingBatchDelete = $state<{ ids: Set<string>; count: number; timeoutId: ReturnType<typeof setTimeout> } | null>(null);

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

	function handleBatchDelete() {
		if (selectedIds.size === 0) return;
		let ids = new Set(selectedIds);
		if (pendingBatchDelete) {
			clearTimeout(pendingBatchDelete.timeoutId);
			for (const id of pendingBatchDelete.ids) {
				ids.add(id);
			}
		}
		const count = ids.size;
		const timeoutId = setTimeout(() => executeBatchDelete(ids), UNDO_DELAY_MS);
		pendingBatchDelete = { ids, count, timeoutId };
		exitSelectMode();
	}

	async function executeBatchDelete(ids: Set<string>) {
		pendingBatchDelete = null;
		await removeEpisodes([...ids]);
	}

	function undoBatchDelete() {
		if (!pendingBatchDelete) return;
		clearTimeout(pendingBatchDelete.timeoutId);
		pendingBatchDelete = null;
	}

	let editShowName = $state('');
	let editArtist = $state('');
	let editTitle = $state('');
	let editContentType = $state<ContentType>('music');

	const garmin = getGarminStatus();

	let collapsedSections = $state<Set<string>>(
		new Set(JSON.parse(localStorage.getItem(STORAGE_KEYS.COLLAPSED_SECTIONS) ?? '[]'))
	);
	let collapsedGroups = $state<Set<string>>(
		new Set(JSON.parse(localStorage.getItem(STORAGE_KEYS.COLLAPSED_GROUPS) ?? '[]'))
	);

	function toggleSection(label: string) {
		if (collapsedSections.has(label)) {
			collapsedSections.delete(label);
		} else {
			collapsedSections.add(label);
		}
		collapsedSections = new Set(collapsedSections);
		localStorage.setItem(STORAGE_KEYS.COLLAPSED_SECTIONS, JSON.stringify([...collapsedSections]));
	}

	function toggleGroup(showName: string) {
		if (collapsedGroups.has(showName)) {
			collapsedGroups.delete(showName);
		} else {
			collapsedGroups.add(showName);
		}
		collapsedGroups = new Set(collapsedGroups);
		localStorage.setItem(STORAGE_KEYS.COLLAPSED_GROUPS, JSON.stringify([...collapsedGroups]));
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

	let visibleEpisodes = $derived.by(() => {
		let result = episodes;
		if (pendingDelete) {
			result = result.filter((ep) => ep.video_id !== pendingDelete!.videoId);
		}
		if (pendingBatchDelete) {
			const ids = pendingBatchDelete.ids;
			result = result.filter((ep) => !ids.has(ep.video_id));
		}
		return result;
	});

	let sections: Section[] = $derived(
		SECTION_ORDER
			.map((label) => {
				const ct = SECTION_CONTENT_TYPE[label];
				const items = visibleEpisodes.filter((ep) => ep.content_type === ct);
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

	function sectionEpisodeIds(section: Section): string[] {
		const ids: string[] = [];
		for (const group of section.groups) {
			for (const ep of group.episodes) ids.push(ep.video_id);
		}
		for (const ep of section.ungrouped) ids.push(ep.video_id);
		return ids;
	}

	function groupEpisodeIds(group: ShowGroup): string[] {
		return group.episodes.map(ep => ep.video_id);
	}

	function toggleSectionSelection(section: Section) {
		const ids = sectionEpisodeIds(section);
		const allSelected = ids.length > 0 && ids.every(id => selectedIds.has(id));
		if (allSelected) {
			for (const id of ids) selectedIds.delete(id);
		} else {
			for (const id of ids) selectedIds.add(id);
		}
		selectedIds = new Set(selectedIds);
	}

	function toggleGroupSelection(group: ShowGroup) {
		const ids = groupEpisodeIds(group);
		const allSelected = ids.length > 0 && ids.every(id => selectedIds.has(id));
		if (allSelected) {
			for (const id of ids) selectedIds.delete(id);
		} else {
			for (const id of ids) selectedIds.add(id);
		}
		selectedIds = new Set(selectedIds);
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
		const duration = ep.duration_seconds ? formatDuration(ep.duration_seconds) : '';
		return duration ? `${duration} - ${size}` : size;
	}

	function startEditing(ep: DownloadedEpisode) {
		editingId = ep.video_id;
		editShowName = ep.show_name ?? '';
		editArtist = ep.artist ?? '';
		editTitle = ep.title;
		editContentType = ep.content_type;
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

	function handleRemove(videoId: string, title: string) {
		if (pendingDelete) {
			clearTimeout(pendingDelete.timeoutId);
			executeDelete(pendingDelete.videoId);
		}
		const timeoutId = setTimeout(() => executeDelete(videoId), UNDO_DELAY_MS);
		pendingDelete = { videoId, title, timeoutId };
	}

	async function executeDelete(videoId: string) {
		pendingDelete = null;
		await removeEpisode(videoId);
	}

	function undoDelete() {
		if (!pendingDelete) return;
		clearTimeout(pendingDelete.timeoutId);
		pendingDelete = null;
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
	{#if selectMode}
		<EpisodeCard
			title={ep.title}
			contentType={ep.content_type}
			subtitle={subtitle(ep)}
			selectable={true}
			selected={selectedIds.has(ep.video_id)}
			onToggle={() => toggleSelected(ep.video_id)}
		/>
	{:else if editingId === ep.video_id}
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
					title="Delete episode"
				>
					✕
				</button>
			{/snippet}
		</EpisodeCard>
	{/if}
{/snippet}

{#if episodes.length === 0}
	<p class="empty">No downloaded episodes</p>
{:else}
	{#if selectMode}
		<div class="select-bar">
			<label class="select-all">
				<input
					type="checkbox"
					checked={selectedIds.size === visibleEpisodes.length && visibleEpisodes.length > 0}
					indeterminate={selectedIds.size > 0 && selectedIds.size < visibleEpisodes.length}
					onchange={() => {
						if (selectedIds.size === visibleEpisodes.length) {
							selectedIds = new Set();
						} else {
							selectedIds = new Set(visibleEpisodes.map(ep => ep.video_id));
						}
					}}
				/>
				All
			</label>
			<button class="btn btn-danger" onclick={handleBatchDelete} disabled={selectedIds.size === 0}>
				Delete ({selectedIds.size})
			</button>
			<button class="btn btn-outline" onclick={exitSelectMode}>Cancel</button>
		</div>
	{:else}
		<div class="select-toggle">
			<button class="btn btn-outline" onclick={enterSelectMode}>Select</button>
		</div>
	{/if}
	{#each sections as section (section.label)}
		{#if selectMode}
			{@const sIds = sectionEpisodeIds(section)}
			{@const sSelected = sIds.filter(id => selectedIds.has(id)).length}
			<div class="section-header">
				<input
					type="checkbox"
					checked={sSelected === sIds.length && sIds.length > 0}
					indeterminate={sSelected > 0 && sSelected < sIds.length}
					onchange={() => toggleSectionSelection(section)}
				/>
				<button class="header-collapse-btn" onclick={() => toggleSection(section.label)}>
					<span class="chevron" class:collapsed={collapsedSections.has(section.label)}>{'\u25BE'}</span>
					{section.label}
					<span class="section-count">{sectionEpisodeCount(section)}</span>
				</button>
			</div>
		{:else}
			<button class="section-header" onclick={() => toggleSection(section.label)}>
				<span class="chevron" class:collapsed={collapsedSections.has(section.label)}>{'\u25BE'}</span>
				{section.label}
				<span class="section-count">{sectionEpisodeCount(section)}</span>
			</button>
		{/if}

		{#if !collapsedSections.has(section.label)}
			{#each section.groups as group (group.showName)}
				<div class="show-group">
					{#if selectMode}
						{@const gIds = groupEpisodeIds(group)}
						{@const gSelected = gIds.filter(id => selectedIds.has(id)).length}
						<div class="show-header">
							<input
								type="checkbox"
								checked={gSelected === gIds.length && gIds.length > 0}
								indeterminate={gSelected > 0 && gSelected < gIds.length}
								onchange={() => toggleGroupSelection(group)}
							/>
							<button class="header-collapse-btn" onclick={() => toggleGroup(group.showName)}>
								<span class="chevron" class:collapsed={collapsedGroups.has(group.showName)}>{'\u25BE'}</span>
								{group.showName}
								<span class="show-meta">
									{group.episodes.length} {group.episodes.length === 1 ? 'episode' : 'episodes'}
									- {formatSize(group.totalSize)}
								</span>
							</button>
						</div>
					{:else}
						<button class="show-header" onclick={() => toggleGroup(group.showName)}>
							<span class="chevron" class:collapsed={collapsedGroups.has(group.showName)}>{'\u25BE'}</span>
							{group.showName}
							<span class="show-meta">
								{group.episodes.length} {group.episodes.length === 1 ? 'episode' : 'episodes'}
								- {formatSize(group.totalSize)}
							</span>
						</button>
					{/if}
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

{#if pendingDelete}
	<div class="undo-toast">
		<span>Deleted {pendingDelete.title}</span>
		<button onclick={undoDelete}>Undo</button>
	</div>
{/if}

{#if pendingBatchDelete}
	<div class="undo-toast">
		<span>Deleted {pendingBatchDelete.count} episodes</span>
		<button onclick={undoBatchDelete}>Undo</button>
	</div>
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
		padding: 0.35rem 0.75rem 0.35rem 2rem;
		min-height: 2rem;
		cursor: pointer;
		text-align: left;
		position: relative;
	}
	.section-header:first-child {
		border-top: none;
	}
	.section-header:hover {
		color: var(--color-text-secondary);
	}
	.header-collapse-btn {
		display: flex;
		align-items: inherit;
		gap: inherit;
		flex: 1;
		background: none;
		border: none;
		font: inherit;
		letter-spacing: inherit;
		text-transform: inherit;
		color: inherit;
		padding: 0;
		cursor: pointer;
		text-align: left;
	}
	.header-collapse-btn:hover {
		color: var(--color-primary);
	}
	.section-header input[type="checkbox"],
	.show-header input[type="checkbox"] {
		position: absolute;
		left: 0.3rem;
		top: 50%;
		transform: translateY(-50%);
		margin: 0;
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
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		background: none;
		border: none;
		font-size: var(--font-size-sm);
		font-weight: 600;
		color: var(--color-text);
		padding: 0.3rem 0.75rem 0.3rem 2rem;
		min-height: 2rem;
		cursor: pointer;
		text-align: left;
		position: relative;
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
	.connect-hint {
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		cursor: default;
		padding: 0.15rem 0.2rem;
	}
	.undo-toast {
		position: fixed;
		bottom: 1.5rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--color-bg-panel);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		padding: 0.5rem 0.75rem;
		font-size: var(--font-size-sm);
		box-shadow: var(--shadow-dialog);
		z-index: 100;
	}
	.undo-toast button {
		background: none;
		border: none;
		color: var(--color-primary);
		font-size: var(--font-size-sm);
		font-weight: 600;
		cursor: pointer;
		padding: 0.15rem 0.4rem;
		border-radius: var(--radius-sm);
		transition: background 0.15s;
	}
	.undo-toast button:hover {
		background: var(--color-primary-light);
	}
</style>
