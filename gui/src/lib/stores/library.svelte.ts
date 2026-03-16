import { call } from '$lib/backend';
import { setActive } from '$lib/stores/progress.svelte';
import { getGarminStatus, refreshGarmin } from '$lib/stores/garmin.svelte';
import type { Library, AddResult, ProcessResult, ShowInfo, ListShowsResult, RenameShowResult, EpisodeUpdates, SearchResult, ChannelVideo, Playlist, AuthStatus } from '$lib/types';

let library = $state<Library>({ queue: [], downloaded: [] });
let loading = $state(false);
let error = $state<string | null>(null);
let processing = $state(false);

export function getLibrary() {
	return {
		get data() { return library; },
		get loading() { return loading; },
		get error() { return error; },
		get processing() { return processing; },
	};
}

export async function refreshLibrary() {
	loading = true;
	error = null;
	try {
		library = await call<Library>('get_library');
	} catch (e: any) {
		error = e?.message ?? String(e);
	} finally {
		loading = false;
	}
}

export async function addToQueue(urls: string[], contentType: string, showName?: string): Promise<AddResult> {
	const result = await call<AddResult>('add_to_queue', {
		urls,
		contentType,
		showName,
	});
	await refreshLibrary();
	return result;
}

export async function removeEpisode(videoId: string) {
	await call('remove_episode', { videoId });
	await refreshLibrary();
}

export async function processQueue(options: {
	chunkDurationSeconds?: number;
	artist?: string;
	keepFull?: boolean;
	noTransfer?: boolean;
} = {}): Promise<ProcessResult> {
	const result = await call<ProcessResult>('process_queue', options);
	await refreshLibrary();
	return result;
}

export function startProcessing(options: {
	noTransfer?: boolean;
} = {}) {
	if (processing) return;
	processing = true;
	setActive(true);

	(async () => {
		try {
			while (library.queue.length > 0) {
				await processQueue({ noTransfer: options.noTransfer });
			}
			await refreshGarmin();
		} finally {
			processing = false;
			setActive(false);
		}
	})();
}

export async function transferEpisode(videoId: string) {
	await call('transfer_episode', { videoId });
	await refreshLibrary();
}

export async function cancelProcessing() {
	await call('cancel');
}

export async function cancelAndRemove(videoId: string) {
	await call('cancel');
	await removeEpisode(videoId);
}

export async function listShows(): Promise<ShowInfo[]> {
	const result = await call<ListShowsResult>('list_shows');
	return result.shows;
}

export async function renameShow(oldName: string, newName: string): Promise<number> {
	const result = await call<RenameShowResult>('rename_show', { oldName, newName });
	await refreshLibrary();
	return result.renamed;
}

export async function editEpisode(videoId: string, updates: EpisodeUpdates): Promise<void> {
	await call('edit_episode', { videoId, updates });
	await refreshLibrary();
}

export async function resyncEpisode(videoId: string): Promise<void> {
	await call('resync_episode', { videoId });
	await refreshLibrary();
}

export async function editQueueEntry(videoId: string, updates: EpisodeUpdates): Promise<void> {
	await call('edit_queue_entry', { videoId, updates });
	await refreshLibrary();
}

export async function searchYouTube(query: string, offset: number = 0): Promise<SearchResult[]> {
	const result = await call<{ results: SearchResult[] }>('search_youtube', { query, offset });
	return result.results;
}

export async function listChannelVideos(channelUrl: string, offset: number = 0): Promise<{ channel_name: string; videos: ChannelVideo[] }> {
	return call<{ channel_name: string; videos: ChannelVideo[] }>('list_channel_videos', { channelUrl, offset });
}

export async function listSubscriptions(offset: number = 0): Promise<SearchResult[]> {
	const result = await call<{ results: SearchResult[] }>('list_subscriptions', { offset });
	return result.results;
}

export async function listHomeFeed(offset: number = 0): Promise<SearchResult[]> {
	const result = await call<{ results: SearchResult[] }>('list_home_feed', { offset });
	return result.results;
}

export async function listLikedVideos(offset: number = 0): Promise<SearchResult[]> {
	const result = await call<{ results: SearchResult[] }>('list_liked_videos', { offset });
	return result.results;
}

export async function listPlaylists(): Promise<Playlist[]> {
	const result = await call<{ playlists: Playlist[] }>('list_playlists');
	return result.playlists;
}

export async function listPlaylistVideos(playlistId: string, offset: number = 0): Promise<SearchResult[]> {
	const result = await call<{ results: SearchResult[] }>('list_playlist_videos', { playlistId, offset });
	return result.results;
}

export async function detectBrowser(): Promise<string | null> {
	const result = await call<{ browser: string | null }>('detect_browser');
	return result.browser;
}

export async function connectCookies(browser?: string): Promise<{ success: boolean; browser?: string; error?: string }> {
	return call('connect_cookies', { browser });
}

export async function getAuthStatus(): Promise<AuthStatus> {
	return call<AuthStatus>('get_auth_status');
}

export async function disconnectAuth(): Promise<void> {
	await call('disconnect_auth');
}
