<script lang="ts">
	import { getProgress } from '$lib/stores/progress.svelte';

	const progress = getProgress();
</script>

{#if progress.active && progress.current}
	<div class="progress-panel">
		<div class="progress-message">{progress.current.message}</div>
		{#if progress.current.percent > 0}
			<div class="progress-bar">
				<div class="progress-fill" style="width: {progress.current.percent}%"></div>
			</div>
		{/if}
	</div>
{/if}

<style>
	.progress-panel {
		padding: 0.5rem 1rem;
		background: var(--color-bg-progress);
		border-top: 1px solid var(--color-border);
	}
	.progress-message {
		font-size: var(--font-size-md);
		color: var(--color-text);
		margin-bottom: 0.3rem;
	}
	.progress-bar {
		height: 6px;
		background: var(--color-border);
		border-radius: var(--radius-sm);
		overflow: hidden;
	}
	.progress-fill {
		height: 100%;
		background: var(--color-primary);
		border-radius: var(--radius-sm);
		transition: width 0.3s;
	}
</style>
