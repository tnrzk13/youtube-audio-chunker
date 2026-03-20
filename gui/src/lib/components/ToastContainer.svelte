<script lang="ts">
	import { getToasts, removeToast } from '$lib/stores/toasts.svelte';

	const toasts = getToasts();
</script>

{#if toasts.list.length > 0}
	<div class="toast-container">
		{#each toasts.list as toast (toast.id)}
			<div
				class="toast toast-{toast.type}"
				role={toast.type === 'error' ? 'alert' : 'status'}
				aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
			>
				<span class="toast-message">{toast.message}</span>
				<button class="toast-close" onclick={() => removeToast(toast.id)} aria-label="Dismiss">&times;</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.toast-container {
		position: fixed;
		bottom: 4rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		z-index: 200;
		pointer-events: none;
	}
	.toast {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius-md);
		font-size: var(--font-size-sm);
		box-shadow: var(--shadow-dialog);
		pointer-events: auto;
		max-width: min(90%, 420px);
		word-break: break-word;
	}
	.toast-error {
		background: var(--color-danger);
		color: #fff;
	}
	.toast-warning {
		background: var(--color-warning, #e6a817);
		color: #000;
	}
	.toast-info {
		background: var(--color-bg-panel);
		border: 1px solid var(--color-border);
		color: var(--color-text);
	}
	.toast-message {
		flex: 1;
	}
	.toast-close {
		background: none;
		border: none;
		color: inherit;
		font-size: var(--font-size-lg);
		cursor: pointer;
		padding: 0 0.2rem;
		line-height: 1;
		opacity: 0.7;
		flex-shrink: 0;
	}
	.toast-close:hover {
		opacity: 1;
	}
</style>
