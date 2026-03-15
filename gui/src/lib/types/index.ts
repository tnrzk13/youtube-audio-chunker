export interface QueueEntry {
	video_id: string;
	url: string;
	title: string;
	added_at: string;
	content_type: string;
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

export type ContentType = 'music' | 'podcast' | 'audiobook';
