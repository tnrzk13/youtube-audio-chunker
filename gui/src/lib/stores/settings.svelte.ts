import { invoke } from '@tauri-apps/api/core';

let settings = $state<Record<string, any>>({});

export function getSettings() {
	return {
		get data() { return settings; },
	};
}

export async function refreshSettings() {
	try {
		settings = await invoke<Record<string, any>>('get_settings');
	} catch {
		settings = {};
	}
}

export async function saveSettings(newSettings: Record<string, any>) {
	await invoke('save_settings', { settings: newSettings });
	settings = newSettings;
}
