import { call } from '$lib/backend';

let settings = $state<Record<string, any>>({});

export function getSettings() {
	return {
		get data() { return settings; },
	};
}

export async function refreshSettings() {
	try {
		settings = await call<Record<string, any>>('get_settings');
	} catch {
		settings = {};
	}
}

export async function saveSettings(newSettings: Record<string, any>) {
	await call('save_settings', { settings: newSettings });
	settings = newSettings;
}
