/**
 * Transport abstraction - uses Tauri invoke() when in the Tauri app,
 * falls back to HTTP fetch() when in a regular browser.
 */

const IS_TAURI = typeof window !== 'undefined' && !!(window as any).__TAURI_INTERNALS__;
// In browser mode, requests go through Vite's dev proxy (see vite.config.ts)
const HTTP_BASE = '';

function toSnakeCase(str: string): string {
	return str.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

function convertKeysToSnakeCase(obj: any): any {
	if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
	if (Array.isArray(obj)) return obj.map(convertKeysToSnakeCase);
	const result: Record<string, any> = {};
	for (const [key, value] of Object.entries(obj)) {
		result[toSnakeCase(key)] = convertKeysToSnakeCase(value);
	}
	return result;
}

export async function call<T = any>(method: string, params: Record<string, any> = {}): Promise<T> {
	if (IS_TAURI) {
		const { invoke } = await import('@tauri-apps/api/core');
		return invoke<T>(method, params);
	}

	const resp = await fetch(`${HTTP_BASE}/rpc`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ method, params: convertKeysToSnakeCase(params) }),
	});
	const data = await resp.json();
	if (data.error) throw new Error(data.error);
	return data.result as T;
}

export type ProgressCallback = (event: any) => void;

export function subscribe(callback: ProgressCallback): () => void {
	if (IS_TAURI) {
		let unlisten: (() => void) | undefined;
		import('@tauri-apps/api/event').then(({ listen }) => {
			listen('sidecar:progress', (event) => callback(event.payload)).then((fn) => {
				unlisten = fn;
			});
		});
		return () => unlisten?.();
	}

	const source = new EventSource(`${HTTP_BASE}/events`);
	source.onmessage = (event) => {
		try {
			callback(JSON.parse(event.data));
		} catch { /* ignore parse errors */ }
	};
	return () => source.close();
}
