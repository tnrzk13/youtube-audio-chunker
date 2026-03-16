<script lang="ts">
	import ContentTypeBadge from './ContentTypeBadge.svelte';
	import type { Snippet } from 'svelte';

	let {
		title,
		contentType,
		subtitle = '',
		syncStatus,
		statusTooltip,
		actions,
	}: {
		title: string;
		contentType: string;
		subtitle?: string;
		syncStatus?: 'synced' | 'queued';
		statusTooltip?: string;
		actions?: Snippet;
	} = $props();

	let statusClass = $derived(
		syncStatus === 'synced' ? 'card-status-synced' : syncStatus === 'queued' ? 'card-status-queued' : ''
	);
</script>

<div class="card {statusClass}">
	{#if syncStatus && statusTooltip}
		<span class="status-tooltip">
			<span class="status-dot {syncStatus}"></span>
			{statusTooltip}
		</span>
	{/if}
	<div class="card-body">
		<div class="card-title">{title}</div>
		<div class="card-meta">
			<ContentTypeBadge {contentType} />
			{#if subtitle}
				<span class="subtitle">{subtitle}</span>
			{/if}
		</div>
	</div>
	{#if actions}
		<div class="card-actions">
			{@render actions()}
		</div>
	{/if}
</div>

<style>
	.card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border-subtle);
		gap: 0.5rem;
		transition: background 0.15s;
		position: relative;
	}
	.card:hover {
		background: var(--color-bg-hover);
	}
	.card:last-child {
		border-bottom: none;
	}
	.status-tooltip {
		display: none;
		position: absolute;
		left: -2px;
		top: -6px;
		transform: translateY(-100%);
		background: var(--color-bg-panel);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-sm);
		padding: 0.2rem 0.45rem;
		font-size: var(--font-size-xs);
		color: var(--color-text-secondary);
		white-space: nowrap;
		align-items: center;
		gap: 0.3rem;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
		z-index: 10;
		pointer-events: none;
	}
	.card:hover .status-tooltip {
		display: flex;
	}
	.status-dot {
		width: 7px;
		height: 7px;
		border-radius: var(--radius-full);
		flex-shrink: 0;
	}
	.status-dot.synced {
		background: var(--color-card-synced);
	}
	.status-dot.queued {
		background: var(--color-card-queued);
	}
	.card-body {
		flex: 1;
		min-width: 0;
	}
	.card-title {
		font-size: var(--font-size-base);
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.card-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.2rem;
	}
	.subtitle {
		font-size: var(--font-size-sm);
		color: var(--color-text-subtitle);
	}
	.card-actions {
		flex-shrink: 0;
	}
</style>
