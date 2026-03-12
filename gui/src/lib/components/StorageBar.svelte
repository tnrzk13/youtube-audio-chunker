<script lang="ts">
	import type { GarminStatus } from '$lib/types';

	let { status }: { status: GarminStatus } = $props();

	let usedBytes = $derived(status.episodes.reduce((sum, ep) => sum + ep.total_size_bytes, 0));
	let totalBytes = $derived(usedBytes + status.available_bytes);
	let usedPercent = $derived(totalBytes > 0 ? (usedBytes / totalBytes) * 100 : 0);
	let freePercent = $derived(100 - usedPercent);

	let statusColor = $derived(
		freePercent < 10 ? 'var(--color-critical)' : freePercent < 20 ? 'var(--color-warning)' : 'var(--color-success)'
	);

	function formatSize(bytes: number): string {
		const mb = bytes / 1_000_000;
		if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
		return `${mb.toFixed(0)} MB`;
	}
</script>

{#if status.connected}
	<div class="storage">
		<div class="bar">
			<div class="bar-fill" style="width: {usedPercent}%"></div>
		</div>
		<div class="label" style="color: {statusColor}">{formatSize(status.available_bytes)} free of {formatSize(totalBytes)}</div>
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
	}
	.bar-fill {
		height: 100%;
		border-radius: var(--radius-sm);
		transition: width 0.3s;
		background: var(--color-bar-fill);
	}
	.label {
		font-size: var(--font-size-xs);
		margin-top: 0.25rem;
		text-align: center;
	}
</style>
