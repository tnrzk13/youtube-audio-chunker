import { describe, it, expect } from 'vitest';
import { computeStorageBreakdown, formatSize } from './storage';
import type { GarminStatus } from '$lib/types';

function makeStatus(overrides: Partial<GarminStatus> = {}): GarminStatus {
	return {
		connected: true,
		episodes: [],
		available_bytes: 0,
		total_bytes: 0,
		...overrides,
	};
}

describe('computeStorageBreakdown', () => {
	it('calculates other bytes from total minus episodes minus free', () => {
		const status = makeStatus({
			total_bytes: 8_000_000_000,
			available_bytes: 3_500_000_000,
			episodes: [
				{ folder_name: 'podcast-1', total_size_bytes: 500_000_000, modified_at: 1000, location: 'Music' },
				{ folder_name: 'podcast-2', total_size_bytes: 1_000_000_000, modified_at: 2000, location: 'Podcasts' },
			],
		});

		const result = computeStorageBreakdown(status);

		expect(result.episodeBytes).toBe(1_500_000_000);
		expect(result.otherBytes).toBe(3_000_000_000);
		expect(result.freeBytes).toBe(3_500_000_000);
		expect(result.totalBytes).toBe(8_000_000_000);
	});

	it('calculates correct percentages', () => {
		const status = makeStatus({
			total_bytes: 10_000_000_000,
			available_bytes: 5_000_000_000,
			episodes: [
				{ folder_name: 'ep', total_size_bytes: 2_000_000_000, modified_at: 1000, location: 'Music' },
			],
		});

		const result = computeStorageBreakdown(status);

		expect(result.episodePercent).toBe(20);
		expect(result.otherPercent).toBe(30);
		expect(result.freePercent).toBe(50);
	});

	it('handles empty watch with no episodes or other files', () => {
		const status = makeStatus({
			total_bytes: 8_000_000_000,
			available_bytes: 8_000_000_000,
			episodes: [],
		});

		const result = computeStorageBreakdown(status);

		expect(result.episodeBytes).toBe(0);
		expect(result.otherBytes).toBe(0);
		expect(result.freeBytes).toBe(8_000_000_000);
		expect(result.freePercent).toBe(100);
	});

	it('handles watch with only other files (e.g. Spotify)', () => {
		const status = makeStatus({
			total_bytes: 8_000_000_000,
			available_bytes: 3_000_000_000,
			episodes: [],
		});

		const result = computeStorageBreakdown(status);

		expect(result.episodeBytes).toBe(0);
		expect(result.otherBytes).toBe(5_000_000_000);
		expect(result.freeBytes).toBe(3_000_000_000);
		expect(result.episodePercent).toBe(0);
		expect(result.otherPercent).toBeCloseTo(62.5);
		expect(result.freePercent).toBeCloseTo(37.5);
	});

	it('handles watch with no other files', () => {
		const status = makeStatus({
			total_bytes: 8_000_000_000,
			available_bytes: 6_000_000_000,
			episodes: [
				{ folder_name: 'ep', total_size_bytes: 2_000_000_000, modified_at: 1000, location: 'Music' },
			],
		});

		const result = computeStorageBreakdown(status);

		expect(result.otherBytes).toBe(0);
		expect(result.otherPercent).toBe(0);
	});

	it('clamps other bytes to zero if rounding causes negative', () => {
		const status = makeStatus({
			total_bytes: 1_000_000,
			available_bytes: 600_000,
			episodes: [
				{ folder_name: 'ep', total_size_bytes: 500_000, modified_at: 1000, location: 'Music' },
			],
		});

		const result = computeStorageBreakdown(status);

		expect(result.otherBytes).toBe(0);
	});

	it('clamps freePercent to zero when episodes exceed reported total', () => {
		const status = makeStatus({
			total_bytes: 1_000_000,
			available_bytes: 100_000,
			episodes: [
				{ folder_name: 'ep', total_size_bytes: 1_200_000, modified_at: 1000, location: 'Music' },
			],
		});

		const result = computeStorageBreakdown(status);

		expect(result.freePercent).toBeGreaterThanOrEqual(0);
	});

	it('returns zero percentages when total_bytes is 0 (disconnected)', () => {
		const status = makeStatus({
			connected: false,
			total_bytes: 0,
			available_bytes: 0,
			episodes: [],
		});

		const result = computeStorageBreakdown(status);

		expect(result.episodePercent).toBe(0);
		expect(result.otherPercent).toBe(0);
		expect(result.freePercent).toBe(100);
		expect(result.totalBytes).toBe(0);
	});

	it('falls back to episodes + available when total_bytes is missing (old backend)', () => {
		const status = {
			connected: true,
			episodes: [
				{ folder_name: 'ep', total_size_bytes: 500_000_000, modified_at: 1000, location: 'Music' },
			],
			available_bytes: 3_500_000_000,
		} as GarminStatus;

		const result = computeStorageBreakdown(status);

		expect(result.totalBytes).toBe(4_000_000_000);
		expect(result.freeBytes).toBe(3_500_000_000);
		expect(result.episodeBytes).toBe(500_000_000);
		expect(result.otherBytes).toBe(0);
		expect(Number.isNaN(result.episodePercent)).toBe(false);
		expect(Number.isNaN(result.freePercent)).toBe(false);
	});

	it('percentages always sum to 100', () => {
		const status = makeStatus({
			total_bytes: 7_643_218_944,
			available_bytes: 2_147_483_648,
			episodes: [
				{ folder_name: 'ep1', total_size_bytes: 1_073_741_824, modified_at: 1000, location: 'Music' },
				{ folder_name: 'ep2', total_size_bytes: 536_870_912, modified_at: 2000, location: 'Podcasts' },
			],
		});

		const result = computeStorageBreakdown(status);

		expect(result.episodePercent + result.otherPercent + result.freePercent).toBeCloseTo(100);
	});
});

describe('formatSize', () => {
	it('formats bytes under 1 GB as MB', () => {
		expect(formatSize(500_000_000)).toBe('500 MB');
	});

	it('formats bytes at or above 1 GB as GB', () => {
		expect(formatSize(1_000_000_000)).toBe('1.0 GB');
		expect(formatSize(3_500_000_000)).toBe('3.5 GB');
	});

	it('formats small values as MB', () => {
		expect(formatSize(50_000_000)).toBe('50 MB');
	});

	it('formats zero', () => {
		expect(formatSize(0)).toBe('0 MB');
	});

	it('formats large values', () => {
		expect(formatSize(8_000_000_000)).toBe('8.0 GB');
	});
});
