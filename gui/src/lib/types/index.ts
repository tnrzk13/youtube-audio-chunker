export interface QueueEntry {
	video_id: string;
	url: string;
	title: string;
	added_at: string;
	content_type: string;
	show_name: string | null;
	artist: string | null;
}

export interface DownloadedEpisode {
	video_id: string;
	url: string;
	title: string;
	folder_name: string;
	chunk_count: number;
	total_size_bytes: number;
	downloaded_at: string;
	synced_at: string | null;
	content_type: string;
	show_name: string | null;
	artist: string | null;
}

export interface Library {
	queue: QueueEntry[];
	downloaded: DownloadedEpisode[];
}

export interface GarminEpisode {
	folder_name: string;
	total_size_bytes: number;
	modified_at: number;
	location: string;
}

export interface GarminStatus {
	connected: boolean;
	episodes: GarminEpisode[];
	available_bytes: number;
	total_bytes: number;
}

export interface ProgressEvent {
	type: string;
	video_id: string;
	message: string;
	percent: number;
}

export interface AddResult {
	added: string[];
	skipped: string[];
}

export interface ProcessResult {
	processed: number;
	transferred: number;
}

export interface TransferResult {
	transferred: number;
}

export interface ShowInfo {
	show_name: string;
	episode_count: number;
	content_types: string[];
}

export interface EpisodeUpdates {
	show_name?: string;
	artist?: string;
	title?: string;
	content_type?: string;
}

export interface RenameShowResult {
	renamed: number;
}

export interface ListShowsResult {
	shows: ShowInfo[];
}

export interface SearchResult {
	video_id: string;
	title: string;
	channel: string;
	duration_seconds: number;
	url: string;
	channel_url: string;
}

export interface ChannelVideo {
	video_id: string;
	title: string;
	duration_seconds: number;
	url: string;
}

export type ContentType = 'music' | 'podcast' | 'audiobook';

export interface Playlist {
	playlist_id: string;
	title: string;
	video_count: number;
}

export type FeedView = 'search' | 'subscriptions' | 'home' | 'liked' | 'playlists' | 'playlist-detail';

export interface AuthStatus {
	method: 'cookies' | 'oauth' | null;
	detail: string | null;
	email?: string | null;
	browser?: string | null;
}
