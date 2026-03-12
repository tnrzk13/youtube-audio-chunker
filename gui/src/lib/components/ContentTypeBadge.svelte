<script lang="ts">
	let { contentType }: { contentType: string } = $props();

	const labels: Record<string, string> = {
		music: 'Music',
		podcast: 'Podcast',
		audiobook: 'Audiobook',
	};
</script>

<span class="badge badge-{contentType}">{labels[contentType] ?? contentType}</span>

<style>
	.badge {
		display: inline-block;
		font-size: var(--font-size-xs);
		padding: 0.1em 0.5em;
		border-radius: var(--radius-sm);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
	.badge-music {
		background: var(--color-badge-music-bg);
		color: var(--color-badge-music-text);
	}
	.badge-podcast {
		background: var(--color-badge-podcast-bg);
		color: var(--color-badge-podcast-text);
	}
	.badge-audiobook {
		background: var(--color-badge-audiobook-bg);
		color: var(--color-badge-audiobook-text);
	}
</style>
