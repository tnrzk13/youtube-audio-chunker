<script lang="ts">
	import type { GarminStatus } from '$lib/types';
	import { computeStorageBreakdown, formatSize } from '$lib/storage';

	let { status }: { status: GarminStatus } = $props();

	let breakdown = $derived(computeStorageBreakdown(status));

	let statusColor = $derived(
		breakdown.freePercent < 10 ? 'var(--color-critical)' : breakdown.freePercent < 20 ? 'var(--color-warning)' : 'var(--color-success)'
	);
</script>

{#if status.connected}
	<div class="storage">
		<div class="bar">
			<div class="bar-episodes" style="width: {breakdown.episodePercent}%"></div>
			<div class="bar-other" style="width: {breakdown.otherPercent}%"></div>
		</div>
		<div class="label" style="color: {statusColor}">{formatSize(breakdown.freeBytes)} free of {formatSize(breakdown.totalBytes)}</div>
		{#if status.total_bytes > 0}
			<div class="legend">
				<span class="legend-item"><span class="swatch swatch-episodes"></span>Synced audio ({formatSize(breakdown.episodeBytes)})</span>
				<span class="legend-item"><span class="swatch swatch-other"></span>Other ({formatSize(breakdown.otherBytes)})</span>
			</div>
		{/if}
	</div>
{/if}

<style>
	.storage {
		padding: 0.5rem 0.75rem;
	}
	.bar {
		height: 8px;
		background: var(--color-bar-track);
		border-radius: var(--radius-sm);
		overflow: hidden;
		display: flex;
	}
	.bar-episodes {
		height: 100%;
		border-radius: var(--radius-sm) 0 0 var(--radius-sm);
		transition: width 0.3s;
		background: var(--color-bar-fill);
	}
	.bar-other {
		height: 100%;
		transition: width 0.3s;
		background: var(--color-bar-other, #c4a35a);
	}
	.label {
		font-size: var(--font-size-xs);
		margin-top: 0.25rem;
		text-align: center;
	}
	.legend {
		display: flex;
		justify-content: center;
		gap: 0.75rem;
		margin-top: 0.25rem;
		font-size: var(--font-size-xs);
		opacity: 0.7;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	.swatch {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 2px;
	}
	.swatch-episodes {
		background: var(--color-bar-fill);
	}
	.swatch-other {
		background: var(--color-bar-other, #c4a35a);
	}
</style>
