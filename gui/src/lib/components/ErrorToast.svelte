<script lang="ts">
	let toasts = $state<{ id: number; message: string }[]>([]);
	let nextId = 0;

	export function showError(message: string) {
		const id = nextId++;
		toasts = [...toasts, { id, message }];
		setTimeout(() => {
			toasts = toasts.filter((t) => t.id !== id);
		}, 8000);
	}

	function dismiss(id: number) {
		toasts = toasts.filter((t) => t.id !== id);
	}
</script>

{#if toasts.length > 0}
	<div class="toast-container">
		{#each toasts as toast (toast.id)}
			<div class="toast">
				<span>{toast.message}</span>
				<button onclick={() => dismiss(toast.id)}>✕</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.toast-container {
		position: fixed;
		top: 1rem;
		right: 1rem;
		z-index: 1000;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 400px;
	}
	.toast {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		background: #d32f2f;
		color: #fff;
		padding: 0.6rem 0.8rem;
		border-radius: 4px;
		font-size: 0.8rem;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
	}
	.toast span {
		flex: 1;
	}
	.toast button {
		background: none;
		border: none;
		color: #fff;
		cursor: pointer;
		font-size: 0.8rem;
		padding: 0;
		opacity: 0.8;
	}
	.toast button:hover {
		opacity: 1;
	}
</style>
