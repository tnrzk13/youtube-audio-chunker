<script lang="ts">
	import type { FeedView, AuthStatus } from '$lib/types';

	let {
		activeView = $bindable('search'),
		authStatus,
		onConnectClick,
		onDisconnectClick,
	}: {
		activeView: FeedView;
		authStatus: AuthStatus;
		onConnectClick: () => void;
		onDisconnectClick: () => void;
	} = $props();

	const items: { view: FeedView; icon: string; label: string }[] = [
		{ view: 'search', icon: '\u{1F50D}', label: 'Search' },
		{ view: 'subscriptions', icon: '\u{1F4E5}', label: 'Subscriptions' },
		{ view: 'home', icon: '\u{1F3E0}', label: 'Home' },
		{ view: 'liked', icon: '\u2665', label: 'Liked' },
		{ view: 'playlists', icon: '\u{1F4CB}', label: 'Playlists' },
	];

	const isConnected = $derived(authStatus.method !== null);

	let popoverOpen = $state(false);
	let authSectionEl = $state<HTMLElement>();

	function handleAccountClick() {
		popoverOpen = !popoverOpen;
	}

	function handleSignOut() {
		popoverOpen = false;
		onDisconnectClick();
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && popoverOpen) {
			popoverOpen = false;
		}
	}

	function handleOutsideClick(event: MouseEvent) {
		if (popoverOpen && authSectionEl && !authSectionEl.contains(event.target as Node)) {
			popoverOpen = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} onclick={handleOutsideClick} />

<nav class="feed-sidebar">
	<ul class="sidebar-items">
		{#each items as item}
			<li>
				<button
					class="sidebar-item"
					class:active={activeView === item.view || (item.view === 'playlists' && activeView === 'playlist-detail')}
					onclick={() => { activeView = item.view; }}
				>
					<span class="sidebar-icon">{item.icon}</span>
					<span class="sidebar-label">{item.label}</span>
				</button>
			</li>
		{/each}
	</ul>
	<div class="sidebar-auth-section" bind:this={authSectionEl}>
		{#if isConnected}
			<button class="account-card" onclick={handleAccountClick} aria-expanded={popoverOpen}>
				<div class="account-avatar">{authStatus.detail?.[0]?.toUpperCase() ?? 'Y'}</div>
				<div class="account-details">
					<span class="account-name">{authStatus.detail}</span>
					{#if authStatus.email}
						<span class="account-email">{authStatus.email}</span>
					{/if}
				</div>
			</button>
			{#if popoverOpen}
				<div class="account-popover">
					<a class="popover-item" href="/settings" onclick={() => { popoverOpen = false; }}>
						Settings
					</a>
					<div class="popover-divider"></div>
					<button class="popover-item sign-out-item" onclick={handleSignOut}>
						Sign out
					</button>
				</div>
			{/if}
		{:else}
			<button class="connect-btn" onclick={onConnectClick}>
				Connect YouTube
			</button>
		{/if}
	</div>
</nav>

<style>
	.feed-sidebar {
		display: flex;
		flex-direction: column;
		width: 200px;
		flex-shrink: 0;
		background: var(--color-bg-panel);
		border-right: 1px solid var(--color-border-subtle);
		padding: 0.5rem 0;
		overflow-y: auto;
	}
	.sidebar-items {
		list-style: none;
		padding: 0;
		margin: 0;
		flex: 1;
	}
	.sidebar-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.75rem;
		background: none;
		border: none;
		border-radius: 0;
		color: var(--color-text-secondary);
		font-size: var(--font-size-md);
		cursor: pointer;
		transition: background 0.1s, color 0.1s;
		text-align: left;
	}
	.sidebar-item:hover {
		background: var(--color-bg-hover);
		color: var(--color-text);
	}
	.sidebar-item.active {
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-weight: 600;
	}
	.sidebar-icon {
		font-size: var(--font-size-base);
		width: 1.4rem;
		text-align: center;
		flex-shrink: 0;
	}
	.sidebar-label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.sidebar-auth-section {
		margin-top: auto;
		border-top: 1px solid var(--color-border-subtle);
		padding: 0.5rem 0.75rem;
		position: relative;
	}
	.account-card {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.35rem 0.4rem;
		background: none;
		border: 1px solid transparent;
		border-radius: var(--radius-md);
		cursor: pointer;
		transition: all 0.15s;
		text-align: left;
	}
	.account-card:hover {
		background: var(--color-bg-hover);
	}
	.account-card[aria-expanded="true"] {
		background: var(--color-bg-hover);
		border-color: var(--color-border);
	}
	.account-avatar {
		width: 28px;
		height: 28px;
		border-radius: var(--radius-full);
		background: var(--color-primary);
		color: #fff;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: var(--font-size-sm);
		font-weight: 600;
		flex-shrink: 0;
	}
	.account-details {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.account-name {
		font-size: var(--font-size-sm);
		font-weight: 500;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.account-email {
		font-size: var(--font-size-xs);
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.account-popover {
		position: absolute;
		bottom: 100%;
		left: 0.5rem;
		right: 0.5rem;
		margin-bottom: 0.25rem;
		background: var(--color-bg-panel);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		box-shadow: var(--shadow-toolbar);
		padding: 0.25rem;
		z-index: 10;
	}
	.popover-item {
		display: flex;
		align-items: center;
		width: 100%;
		padding: 0.4rem 0.5rem;
		background: none;
		border: none;
		border-radius: var(--radius-sm, 4px);
		font-size: var(--font-size-sm);
		color: var(--color-text-secondary);
		text-decoration: none;
		cursor: pointer;
		transition: all 0.1s;
		text-align: left;
	}
	.popover-item:hover {
		background: var(--color-bg-hover);
		color: var(--color-text);
	}
	.popover-divider {
		height: 1px;
		background: var(--color-border-subtle);
		margin: 0.2rem 0;
	}
	.sign-out-item:hover {
		color: var(--color-danger);
	}
	.connect-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		color: var(--color-text-secondary);
		font-size: var(--font-size-sm);
		cursor: pointer;
		padding: 0.35rem 0.5rem;
		transition: all 0.15s;
	}
	.connect-btn:hover {
		background: var(--color-bg-hover);
		color: var(--color-text);
		border-color: var(--color-primary);
	}
</style>
