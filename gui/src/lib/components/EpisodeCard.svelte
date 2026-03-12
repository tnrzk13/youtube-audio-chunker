<script lang="ts">
	import ContentTypeBadge from './ContentTypeBadge.svelte';
	import type { Snippet } from 'svelte';

	let {
		title,
		contentType,
		subtitle = '',
		actions,
	}: {
		title: string;
		contentType: string;
		subtitle?: string;
		actions?: Snippet;
	} = $props();
</script>

<div class="card">
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
	}
	.card:hover {
		background: var(--color-bg-hover);
	}
	.card:last-child {
		border-bottom: none;
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
