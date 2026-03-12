import { listen } from '@tauri-apps/api/event';
import type { ProgressEvent } from '$lib/types';

let current = $state<ProgressEvent | null>(null);
let active = $state(false);

export function getProgress() {
	return {
		get current() { return current; },
		get active() { return active; },
	};
}

export function setActive(value: boolean) {
	active = value;
	if (!value) current = null;
}

export function initProgressListener() {
	return listen<ProgressEvent>('sidecar:progress', (event) => {
		current = event.payload;
	});
}
