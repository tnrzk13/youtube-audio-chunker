type ToastType = 'error' | 'warning' | 'info';

interface Toast {
	id: number;
	message: string;
	type: ToastType;
}

const DISMISS_MS: Record<ToastType, number> = {
	error: 5000,
	warning: 3000,
	info: 3000,
};

let nextId = 0;
let toasts = $state<Toast[]>([]);

export function getToasts() {
	return {
		get list() { return toasts; },
	};
}

export function addToast(message: string, type: ToastType) {
	const id = nextId++;
	toasts = [...toasts, { id, message, type }];
	setTimeout(() => removeToast(id), DISMISS_MS[type]);
}

export function removeToast(id: number) {
	toasts = toasts.filter(t => t.id !== id);
}
