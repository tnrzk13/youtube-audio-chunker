# Non-Blocking Add Flow

## Problem

When a user pastes a YouTube URL and clicks Add, the entire form (textarea, button, content type selector) is disabled for several seconds while the backend calls `extract_metadata` via yt-dlp. This prevents adding multiple videos in quick succession. The same blocking applies when adding selected videos from search results.

## Decision: Sequential Processing, Non-Blocking Add

Parallel downloading was considered but rejected:
- YouTube rate-limits concurrent downloads from the same IP
- The backend holds `_library_lock` during `process_queue`, so concurrent processing would need lock-free library writes
- Progress reporting for multiple simultaneous videos adds UI complexity
- CPU contention during ffmpeg split/tag on a desktop machine

The real bottleneck is the add operation, not the processing pipeline. Making `addToQueue` non-blocking lets users paste URLs freely while the queue processes sequentially in the background.

## Design

### Frontend - AddEpisodeForm Changes

`handleUrlSubmit()` and `handleAddSelected()` become fire-and-forget:

1. Clear the input and re-enable the form immediately (don't await the backend call)
2. Run `addToQueue` + `startProcessing` in the background via an unawaited IIFE or void promise
3. On success: queue list updates automatically via `refreshLibrary()` (already called inside `addToQueue`)
4. On failure: show a transient error toast (5000ms auto-dismiss)
5. On all-skipped (duplicates): show a warning toast. Do not call `startProcessing` (nothing new to process). This fixes an existing bug in `handleAddSelected` which calls `startProcessing` unconditionally (line 208), unlike `handleUrlSubmit` which returns early on all-skipped (line 98).

The `submitting` state is removed from the add flows. The form always stays interactive. Both `handleUrlSubmit` and `handleAddSelected` stop writing to the inline `errorMsg` entirely - all their user-facing messages go through toasts.

**`handleSubmit` dispatcher:** `handleUrlSubmit()` fires its background work in an unawaited void IIFE and returns immediately. `handleSearch()` remains awaited since the user needs to see search results before acting. `handleSubmit` can await both - `handleUrlSubmit` just returns without blocking.

**Search results on add:** When the user clicks "Add selected" from search results, `dismissResults()` runs immediately (before `addToQueue` resolves). The user committed to the action; errors surface via toast.

**Search/channel errors stay inline.** Only the add-related errors move to toasts. `handleSearch()`, `handleBrowseChannel()`, and `loadMoreResults()` continue writing to the inline `errorMsg` since those errors are contextual to the search panel the user is looking at.

### Frontend - Toast Notification Store

A lightweight reactive store (`toasts.svelte.ts`):
- `addToast(message, type)` where type is `'error' | 'warning' | 'info'`
- Toasts auto-dismiss: errors after 5000ms, warnings/info after 3000ms
- Toasts are manually dismissible (click to close)
- A `ToastContainer.svelte` component renders active toasts, positioned fixed at the bottom of the viewport
- Error toasts use `role="alert"` and `aria-live="assertive"`; other toasts use `role="status"` and `aria-live="polite"`

This replaces the inline `errorMsg` only for background add operations.

### Frontend - Processing (No Changes Needed)

`startProcessing()` already handles re-entrancy via `if (processing) return`. The processing loop checks `library.queue.length > 0` after each `processQueue()` call, which triggers `refreshLibrary()`.

**Timing window:** If the user adds URL1 (starts processing) then quickly adds URL2, the processing loop may finish all URL1 items and exit (`processing = false`) before URL2's `addToQueue` completes on the backend. This self-heals: the fire-and-forget handler for URL2 calls `startProcessing()` after its `addToQueue` resolves, which starts a new processing loop since `processing` is now `false`.

### Backend (No Changes Needed)

The sequential `process_queue` pipeline, `_library_lock`, and `extract_metadata` all stay as-is.

`add_to_queue` is synchronous in the sidecar (not in `_ASYNC_METHODS`), which means it blocks the sidecar's main stdin-reading loop during `extract_metadata`. While one `add_to_queue` is in flight, no other JSON-RPC request can be dispatched - including `get_library`. The Tauri `Mutex<SidecarManager>` adds a second layer of serialization. Multiple concurrent `addToQueue` calls from the frontend will serialize through both layers.

This is acceptable because the frontend fire-and-forget pattern decouples UI responsiveness from backend serialization - the user never waits. Moving `add_to_queue` to `_ASYNC_METHODS` (so the sidecar main loop stays responsive during metadata extraction) is a possible future improvement but out of scope here.

## Files Changed

- `gui/src/lib/components/AddEpisodeForm.svelte` - Fire-and-forget add, replace inline add error with toasts
- `gui/src/lib/stores/toasts.svelte.ts` - New toast notification store
- `gui/src/lib/components/ToastContainer.svelte` - New toast UI component
- `gui/src/routes/+page.svelte` - Mount ToastContainer
