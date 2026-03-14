// Apply saved theme to DOM before first render
if (typeof localStorage !== 'undefined' && localStorage.getItem('theme') === 'dark') {
	document.documentElement.setAttribute('data-theme', 'dark');
}

let current = $state<'light' | 'dark'>(
	(typeof localStorage !== 'undefined' && localStorage.getItem('theme') === 'dark')
		? 'dark'
		: 'light'
);

export function getTheme() {
	return {
		get current() { return current; },
		get isDark() { return current === 'dark'; },
	};
}

export function toggleTheme() {
	current = current === 'dark' ? 'light' : 'dark';
	if (current === 'dark') {
		document.documentElement.setAttribute('data-theme', 'dark');
	} else {
		document.documentElement.removeAttribute('data-theme');
	}
	localStorage.setItem('theme', current);
}
