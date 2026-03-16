export const CONTENT_TYPE_OPTIONS = [
	{ value: 'music', label: 'Music' },
	{ value: 'podcast', label: 'Podcast' },
	{ value: 'audiobook', label: 'Audiobook' },
] as const;

export const STORAGE_KEYS = {
	COLLAPSED_SECTIONS: 'collapsed-sections',
	COLLAPSED_GROUPS: 'collapsed-groups',
} as const;
