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
		font-size: 0.7rem;
		padding: 0.1em 0.5em;
		border-radius: 4px;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
	.badge-music {
		background: #e3f2fd;
		color: #1565c0;
	}
	.badge-podcast {
		background: #f3e5f5;
		color: #7b1fa2;
	}
	.badge-audiobook {
		background: #fff3e0;
		color: #e65100;
	}
</style>
