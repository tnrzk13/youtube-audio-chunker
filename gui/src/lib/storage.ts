import type { GarminStatus } from '$lib/types';

export interface StorageBreakdown {
	episodeBytes: number;
	otherBytes: number;
	freeBytes: number;
	totalBytes: number;
	episodePercent: number;
	otherPercent: number;
	freePercent: number;
}

export function computeStorageBreakdown(status: GarminStatus): StorageBreakdown {
	const episodeBytes = status.episodes.reduce((sum, ep) => sum + ep.total_size_bytes, 0);
	const freeBytes = status.available_bytes;
	const totalBytes = status.total_bytes || (episodeBytes + freeBytes);

	if (totalBytes <= 0) {
		return {
			episodeBytes: 0,
			otherBytes: 0,
			freeBytes: 0,
			totalBytes: 0,
			episodePercent: 0,
			otherPercent: 0,
			freePercent: 100,
		};
	}

	const otherBytes = Math.max(0, totalBytes - episodeBytes - freeBytes);
	const episodePercent = (episodeBytes / totalBytes) * 100;
	const otherPercent = (otherBytes / totalBytes) * 100;
	const freePercent = Math.max(0, 100 - episodePercent - otherPercent);

	return { episodeBytes, otherBytes, freeBytes, totalBytes, episodePercent, otherPercent, freePercent };
}

export function formatSize(bytes: number): string {
	const mb = bytes / 1_000_000;
	if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
	return `${mb.toFixed(0)} MB`;
}
