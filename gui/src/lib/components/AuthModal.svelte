<script lang="ts">
	import { connectCookies, detectBrowser } from '$lib/stores/library.svelte';

	let {
		open = $bindable(false),
		onSuccess,
	}: {
		open: boolean;
		onSuccess: () => void;
	} = $props();

	let connecting = $state(false);
	let errorMsg = $state('');
	let detectedBrowser = $state('');

	async function handleCookies() {
		connecting = true;
		errorMsg = '';
		try {
			const result = await connectCookies();
			if (result.success) {
				detectedBrowser = result.browser ?? '';
				open = false;
				onSuccess();
			} else {
				errorMsg = result.error ?? 'Failed to connect';
			}
		} catch (e: any) {
			errorMsg = e?.message ?? String(e);
		} finally {
			connecting = false;
		}
	}

	function handleClose() {
		open = false;
		errorMsg = '';
	}
</script>

{#if open}
	<div class="modal-overlay" onclick={handleClose} role="presentation">
		<div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
			<h2>Connect YouTube Account</h2>
			<p class="modal-desc">
				Connect your YouTube account to browse subscriptions, liked videos, and playlists.
			</p>

			<div class="auth-options">
				<button
					class="auth-option"
					onclick={handleCookies}
					disabled={connecting}
				>
					<span class="option-icon">{'\u{1F36A}'}</span>
					<div class="option-text">
						<span class="option-title">Use Browser Cookies</span>
						<span class="option-hint">Recommended - auto-detects your logged-in browser</span>
					</div>
				</button>

				<div class="auth-option disabled-option">
					<span class="option-icon">{'\u{1F510}'}</span>
					<div class="option-text">
						<span class="option-title">Sign in with Google</span>
						<span class="option-hint">Coming soon - OAuth with your own API credentials</span>
					</div>
				</div>
			</div>

			{#if connecting}
				<div class="modal-status">Detecting browser cookies...</div>
			{/if}
			{#if errorMsg}
				<div class="modal-error">{errorMsg}</div>
			{/if}

			<button class="modal-close" onclick={handleClose}>Cancel</button>
		</div>
	</div>
{/if}

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}
	.modal {
		background: var(--color-bg-panel);
		border-radius: var(--radius-lg);
		padding: 1.5rem;
		width: min(90%, 420px);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
	}
	h2 {
		margin: 0 0 0.5rem;
		font-size: var(--font-size-lg);
		font-weight: 600;
	}
	.modal-desc {
		font-size: var(--font-size-sm);
		color: var(--color-text-secondary);
		margin: 0 0 1rem;
	}
	.auth-options {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
	.auth-option {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-page);
		cursor: pointer;
		text-align: left;
		transition: all 0.15s;
		color: inherit;
	}
	.auth-option:hover:not(:disabled):not(.disabled-option) {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.auth-option:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.disabled-option {
		opacity: 0.5;
		cursor: default;
	}
	.option-icon {
		font-size: 1.25rem;
		flex-shrink: 0;
		margin-top: 0.1rem;
	}
	.option-text {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.option-title {
		font-size: var(--font-size-md);
		font-weight: 500;
	}
	.option-hint {
		font-size: var(--font-size-xs);
		color: var(--color-text-muted);
	}
	.modal-status {
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
	}
	.modal-error {
		font-size: var(--font-size-sm);
		color: var(--color-danger);
		margin-bottom: 0.5rem;
	}
	.modal-close {
		font-size: var(--font-size-md);
		padding: 0.35rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: none;
		color: var(--color-text-secondary);
		cursor: pointer;
		transition: all 0.15s;
	}
	.modal-close:hover {
		background: var(--color-bg-hover);
		color: var(--color-text);
	}
</style>
