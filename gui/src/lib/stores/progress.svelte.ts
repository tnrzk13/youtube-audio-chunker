import { subscribe } from '$lib/backend';
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
	return subscribe((event: ProgressEvent) => {
		current = event;
	});
}
