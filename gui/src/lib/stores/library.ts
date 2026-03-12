import { invoke } from '@tauri-apps/api/core';
import type { Library, AddResult, ProcessResult } from '$lib/types';

let library = $state<Library>({ queue: [], downloaded: [] });
let loading = $state(false);
let error = $state<string | null>(null);

export function getLibrary() {
	return {
		get data() { return library; },
		get loading() { return loading; },
		get error() { return error; },
	};
}

export async function refreshLibrary() {
	loading = true;
	error = null;
	try {
		library = await invoke<Library>('get_library');
	} catch (e: any) {
		error = e?.message ?? String(e);
	} finally {
		loading = false;
	}
}

export async function addToQueue(urls: string[], contentType: string): Promise<AddResult> {
	const result = await invoke<AddResult>('add_to_queue', {
		urls,
		contentType,
	});
	await refreshLibrary();
	return result;
}

export async function removeEpisode(videoId: string) {
	await invoke('remove_episode', { videoId });
	await refreshLibrary();
}

export async function processQueue(options: {
	chunkDurationSeconds?: number;
	artist?: string;
	keepFull?: boolean;
	noTransfer?: boolean;
} = {}): Promise<ProcessResult> {
	const result = await invoke<ProcessResult>('process_queue', options);
	await refreshLibrary();
	return result;
}
