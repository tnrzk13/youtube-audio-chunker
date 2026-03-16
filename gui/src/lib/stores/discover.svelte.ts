import { call } from '$lib/backend';
import type { Topic, SearchResult } from '$lib/types';

let topics = $state<Topic[]>([]);
let selectedTopic = $state<Topic | null>(null);
let results = $state<SearchResult[]>([]);
let loading = $state(false);
let extracting = $state(false);
let nextPageToken = $state<string | null>(null);

export function getDiscoverState() {
	return {
		get topics() { return topics; },
		get selectedTopic() { return selectedTopic; },
		get results() { return results; },
		get loading() { return loading; },
		get extracting() { return extracting; },
		get nextPageToken() { return nextPageToken; },
	};
}

export function selectTopic(topic: Topic | null) {
	selectedTopic = topic;
	if (!topic) {
		results = [];
		nextPageToken = null;
	}
}

export async function refreshTopics() {
	const data = await call<{ topics: Topic[] }>('get_topics');
	topics = data.topics;
}

export async function searchTopic(topicId: string, pageToken?: string) {
	loading = true;
	try {
		const data = await call<{ results: SearchResult[]; next_page_token: string | null }>(
			'search_topic',
			{ topicId, pageToken }
		);
		if (pageToken) {
			results = [...results, ...data.results];
		} else {
			results = data.results;
		}
		nextPageToken = data.next_page_token;
	} finally {
		loading = false;
	}
}

export async function createTopic(name: string, searchQuery: string) {
	const data = await call<{ topics: Topic[] }>('create_topic', { name, searchQuery });
	topics = data.topics;
}

export async function updateTopic(topicId: string, name?: string, searchQuery?: string) {
	await call('update_topic', { topicId, name, searchQuery });
	await refreshTopics();
}

export async function deleteTopic(topicId: string) {
	await call('delete_topic', { topicId });
	topics = topics.filter(t => t.id !== topicId);
	if (selectedTopic?.id === topicId) {
		selectedTopic = null;
		results = [];
	}
}

export async function dismissVideo(videoId: string) {
	await call('dismiss_video', { videoId });
	results = results.filter(r => r.video_id !== videoId);
}

export async function extractTopics() {
	extracting = true;
	try {
		const data = await call<{ topics: Topic[]; new_count: number }>('extract_topics');
		topics = data.topics;
		return data.new_count;
	} finally {
		extracting = false;
	}
}
