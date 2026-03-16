<script lang="ts">
	import { listPlaylists } from '$lib/stores/library.svelte';
	import type { Playlist, AuthStatus } from '$lib/types';

	let {
		authStatus,
		onSelectPlaylist,
		onAuthRequired,
	}: {
		authStatus: AuthStatus;
		onSelectPlaylist: (playlistId: string, title: string) => void;
		onAuthRequired: () => void;
	} = $props();

	let playlists = $state<Playlist[]>([]);
	let loading = $state(false);
	let errorMsg = $state('');
	let initialized = $state(false);

	$effect(() => {
		if (authStatus.method && !initialized) {
			loadPlaylists();
		}
	});

	async function loadPlaylists() {
		if (!authStatus.method) {
			onAuthRequired();
			return;
		}
		loading = true;
		errorMsg = '';
		initialized = true;
		try {
			playlists = await listPlaylists();
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			loading = false;
		}
	}
</script>

<div class="playlist-grid-view">
	<div class="playlist-header">
		<span class="playlist-title">Playlists</span>
		<button class="refresh-btn" onclick={loadPlaylists} disabled={loading}>
			{loading ? 'Loading...' : 'Refresh'}
		</button>
	</div>

	{#if errorMsg}
		<div class="playlist-error">{errorMsg}</div>
	{/if}

	{#if loading && playlists.length === 0}
		<div class="playlist-loading">Loading playlists...</div>
	{:else if !initialized}
		<div class="playlist-empty">
			<button class="load-btn" onclick={loadPlaylists}>Load Playlists</button>
		</div>
	{:else if playlists.length === 0}
		<div class="playlist-empty">No playlists found</div>
	{:else}
		<div class="playlist-list">
			{#each playlists as pl}
				<button class="playlist-card" onclick={() => onSelectPlaylist(pl.playlist_id, pl.title)}>
					<div class="playlist-name">{pl.title}</div>
					<div class="playlist-count">{pl.video_count} videos</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.playlist-grid-view {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		flex: 1;
	}
	.playlist-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		flex-shrink: 0;
	}
	.playlist-title {
		font-size: var(--font-size-md);
		font-weight: 600;
		color: var(--color-text-secondary);
		flex: 1;
	}
	.refresh-btn {
		font-size: var(--font-size-sm);
		padding: 0.2rem 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: none;
		color: var(--color-text-secondary);
		cursor: pointer;
		transition: all 0.15s;
	}
	.refresh-btn:hover:not(:disabled) {
		background: var(--color-bg-hover);
	}
	.refresh-btn:disabled {
		opacity: 0.5;
	}
	.load-btn {
		font-size: var(--font-size-md);
		padding: 0.4rem 1rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius-md);
		background: var(--color-primary);
		color: #fff;
		cursor: pointer;
		transition: all 0.15s;
	}
	.load-btn:hover {
		background: var(--color-primary-hover);
	}
	.playlist-error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		padding: 0.3rem 0.75rem;
	}
	.playlist-loading, .playlist-empty {
		padding: 2rem 0.75rem;
		text-align: center;
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
	.playlist-list {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.playlist-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.6rem 0.75rem;
		border: 1px solid var(--color-border-light);
		border-radius: var(--radius-md);
		background: var(--color-bg-page);
		cursor: pointer;
		transition: all 0.1s;
		text-align: left;
		color: inherit;
	}
	.playlist-card:hover {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.playlist-name {
		font-size: var(--font-size-md);
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
		min-width: 0;
	}
	.playlist-count {
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		flex-shrink: 0;
		margin-left: 0.5rem;
	}
</style>
