<script lang="ts">
	import type { GarminStatus } from '$lib/types';
	import { computeStorageBreakdown, formatSize } from '$lib/storage';

	let { status }: { status: GarminStatus } = $props();

	let breakdown = $derived(computeStorageBreakdown(status));

	let statusColor = $derived(
		breakdown.freePercent < 10
			? 'var(--color-critical)'
			: breakdown.freePercent < 20
				? 'var(--color-warning)'
				: 'var(--color-success)'
	);
</script>

{#if !status.connected}
	<div class="strip disconnected">
		<span class="status-label">
			<span class="dot"></span>
			Watch disconnected
		</span>
	</div>
{:else}
	<div class="strip">
		<span class="status-label">
			<span class="dot connected"></span>
			Connected
		</span>
		{#if status.total_bytes > 0}
			<div class="storage-inline">
				<div class="bar">
					<div class="bar-episodes" style="width: {breakdown.episodePercent}%"></div>
					<div class="bar-other" style="width: {breakdown.otherPercent}%"></div>
				</div>
				<span class="storage-label" style="color: {statusColor}">
					{formatSize(breakdown.freeBytes)} free of {formatSize(breakdown.totalBytes)}
				</span>
				<div class="storage-tooltip">
					<div class="tooltip-row">
						<span class="swatch swatch-episodes"></span>
						<span>Synced audio</span>
						<span class="tooltip-size">{formatSize(breakdown.episodeBytes)} ({breakdown.episodePercent.toFixed(0)}%)</span>
					</div>
					<div class="tooltip-row">
						<span class="swatch swatch-other"></span>
						<span>Other files</span>
						<span class="tooltip-size">{formatSize(breakdown.otherBytes)} ({breakdown.otherPercent.toFixed(0)}%)</span>
					</div>
					<div class="tooltip-row">
						<span class="swatch swatch-free"></span>
						<span>Free</span>
						<span class="tooltip-size">{formatSize(breakdown.freeBytes)} ({breakdown.freePercent.toFixed(0)}%)</span>
					</div>
				</div>
			</div>
		{/if}
	</div>
{/if}

<style>
	.strip {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.35rem max(0.75rem, calc((100% - 700px) / 2));
		background: var(--color-bg-page);
		border-bottom: 1px solid var(--color-border-subtle);
		gap: 1rem;
	}
	.disconnected {
		color: var(--color-text-muted);
	}
	.status-label {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--font-size-sm);
		white-space: nowrap;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: var(--radius-full);
		background: var(--color-border-light);
		flex-shrink: 0;
	}
	.dot.connected {
		background: var(--color-success);
	}
	.storage-inline {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: 1;
		max-width: 300px;
		position: relative;
	}
	.bar {
		flex: 1;
		height: 6px;
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
		background: var(--color-bar-other);
	}
	.storage-label {
		font-size: var(--font-size-xs);
		white-space: nowrap;
	}
	.storage-tooltip {
		display: none;
		position: absolute;
		top: 100%;
		right: 0;
		margin-top: 0.25rem;
		background: var(--color-bg-panel);
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-md);
		padding: 0.5rem 0.65rem;
		font-size: var(--font-size-xs);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		z-index: 20;
		min-width: 200px;
	}
	.storage-inline:hover .storage-tooltip {
		display: block;
	}
	.tooltip-row {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.15rem 0;
	}
	.tooltip-size {
		margin-left: auto;
		opacity: 0.7;
	}
	.swatch {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 2px;
		flex-shrink: 0;
	}
	.swatch-episodes {
		background: var(--color-bar-fill);
	}
	.swatch-other {
		background: var(--color-bar-other);
	}
	.swatch-free {
		background: var(--color-bar-track);
	}
</style>
