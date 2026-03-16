<script lang="ts">
	import type { ContentType } from '$lib/types';
	import { CONTENT_TYPE_OPTIONS } from '$lib/constants';

	let {
		value = $bindable(),
		disabled = false,
		id = undefined,
	}: {
		value: ContentType;
		disabled?: boolean;
		id?: string;
	} = $props();
</script>

<select bind:value {disabled} {id}>
	{#each CONTENT_TYPE_OPTIONS as option}
		<option value={option.value}>{option.label}</option>
	{/each}
</select>

<style>
	select {
		font-size: inherit;
		padding: 0.25rem 0.4rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-panel);
		transition: border-color 0.15s;
	}
	select:focus {
		outline: none;
		border-color: var(--color-primary);
	}
</style>
