import { call } from '$lib/backend';

export interface Settings {
	youtube_api_key?: string;
	anthropic_api_key?: string;
	openai_api_key?: string;
	topic_provider?: string;
	topic_model?: string;
	youtube_auth_method?: string;
	youtube_cookies_browser?: string;
	youtube_account_name?: string;
	youtube_account_email?: string;
	_env_keys?: string[];
	[key: string]: any;
}

let settings = $state<Settings>({});

export function getSettings() {
	return {
		get data() { return settings; },
	};
}

export async function refreshSettings() {
	try {
		settings = await call<Settings>('get_settings');
	} catch {
		settings = {};
	}
}

export async function saveSettings(newSettings: Settings) {
	await call('save_settings', { settings: newSettings });
	settings = newSettings;
}
