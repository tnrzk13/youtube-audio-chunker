import { call } from '$lib/backend';
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
		status = await call<GarminStatus>('get_garmin_status');
	} catch {
		status = { connected: false, episodes: [], available_bytes: 0, total_bytes: 0 };
	} finally {
		loading = false;
	}
}

export async function removeFromGarmin(folderName: string) {
	await call('remove_from_garmin', { folderName });
	await refreshGarmin();
}

export async function removeFromGarminBatch(folderNames: string[]): Promise<{ removed: string[]; failed: { folder_name: string; error: string }[] }> {
	const result = await call<{ removed: string[]; failed: { folder_name: string; error: string }[] }>('remove_from_garmin_batch', { folderNames });
	await refreshGarmin();
	return result;
}

export async function transferUnsynced(): Promise<TransferResult> {
	const result = await call<TransferResult>('transfer_unsynced');
	await refreshGarmin();
	return result;
}
