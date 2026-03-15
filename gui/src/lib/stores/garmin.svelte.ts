import { invoke } from '@tauri-apps/api/core';
import type { GarminStatus, TransferResult } from '$lib/types';

let status = $state<GarminStatus>({ connected: false, episodes: [], available_bytes: 0, total_bytes: 0 });
let loading = $state(false);

export function getGarminStatus() {
	return {
		get data() { return status; },
		get loading() { return loading; },
	};
}

export async function refreshGarmin() {
	loading = true;
	try {
		status = await invoke<GarminStatus>('get_garmin_status');
	} catch {
		status = { connected: false, episodes: [], available_bytes: 0, total_bytes: 0 };
	} finally {
		loading = false;
	}
}

export async function removeFromGarmin(folderName: string) {
	await invoke('remove_from_garmin', { folderName });
	await refreshGarmin();
}

export async function transferUnsynced(): Promise<TransferResult> {
	const result = await invoke<TransferResult>('transfer_unsynced');
	await refreshGarmin();
	return result;
}
