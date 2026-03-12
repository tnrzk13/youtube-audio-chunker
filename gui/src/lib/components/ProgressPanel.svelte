<script lang="ts">
	import { getProgress } from '$lib/stores/progress';

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
		background: #f5f5f5;
		border-top: 1px solid #ddd;
	}
	.progress-message {
		font-size: 0.8rem;
		color: #333;
		margin-bottom: 0.3rem;
	}
	.progress-bar {
		height: 6px;
		background: #ddd;
		border-radius: 3px;
		overflow: hidden;
	}
	.progress-fill {
		height: 100%;
		background: #1976d2;
		border-radius: 3px;
		transition: width 0.3s;
	}
</style>
