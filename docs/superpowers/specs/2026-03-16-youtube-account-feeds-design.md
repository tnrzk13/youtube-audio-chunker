# YouTube Account Feeds

Browse subscriptions, home feed, liked videos, and playlists from within the app, with the option to download them through the existing pipeline.

## Authentication

Two auth providers, one interface. Both produce authenticated yt-dlp calls that can access private feeds.

### Browser Cookies (primary path)

- yt-dlp's `--cookies-from-browser` flag extracts cookies from a locally installed browser
- Auto-detect order: Chrome > Firefox > Chromium > Edge > Brave
- Store detected browser name in `settings.json` to avoid re-detection
- User can override browser choice in Settings

### YouTube Data API v3 (portable path)

- OAuth 2.0 flow - app opens system browser for Google sign-in, receives auth code
- Store refresh token in `settings.json`
- Users provide their own Google Cloud OAuth client ID and secret (no shipped credentials)
- Used for listing subscriptions, liked videos, playlists via the official API
- Downloads still go through yt-dlp (using OAuth token or cookies for auth)

### Auth Trigger

On-demand. Sidebar feed items are always visible. Clicking one without auth shows a modal:
- Title: "Connect YouTube Account"
- Two options: "Use Browser Cookies (recommended)" and "Sign in with Google"
- On success, store auth method + details in `settings.json`, then load the feed
- Subsequent visits use stored auth silently

## UI: Sidebar Navigation

A persistent left sidebar replaces the current single-view layout.

### Sidebar Items

| Item | Icon | Description |
|------|------|-------------|
| Search | Magnifying glass | Default view. Existing search + URL input behavior, unchanged |
| Subscriptions | Inbox | Latest uploads from subscribed channels |
| Home | House | YouTube algorithmic recommendations |
| Liked | Heart | User's liked videos |
| Playlists | List | User's playlists (loads playlist grid, click to drill into videos) |

Bottom of sidebar: "Connect YouTube" link showing auth status.

### Layout Behavior

- Sidebar is always visible on screens >= 750px
- Selecting a feed replaces the content in the main area (search input + results area)
- Queue and Downloaded lists remain visible below the feed content
- The existing two-column layout still activates when search results are showing
- Below 750px: sidebar collapses to a hamburger menu icon in the toolbar

### Playlists View

Single "Playlists" entry in sidebar. Clicking it loads a grid/list of playlists in the main content area (name, video count). Clicking a playlist drills into its videos, shown as a standard video list with the same select-and-add-to-queue interaction as search results.

## Backend: Feed Handlers

### New Sidecar Methods

All methods return `SearchResult`-shaped objects so the frontend reuses existing result rendering.

| Method | Params | Returns |
|--------|--------|---------|
| `list_subscriptions(offset)` | `offset: int` | `{results: SearchResult[]}` |
| `list_home_feed(offset)` | `offset: int` | `{results: SearchResult[]}` |
| `list_liked_videos(offset)` | `offset: int` | `{results: SearchResult[]}` |
| `list_playlists()` | none | `{playlists: Playlist[]}` |
| `list_playlist_videos(playlist_id, offset)` | `playlist_id: str, offset: int` | `{results: SearchResult[]}` |
| `detect_browser()` | none | `{browser: str}` |
| `connect_cookies(browser?)` | `browser: str (optional)` | `{success: bool, browser: str}` |
| `connect_oauth(client_id, client_secret, auth_code)` | OAuth params | `{success: bool}` |
| `get_auth_status()` | none | `{method: str, detail: str} or null` |

### yt-dlp Feed URLs (cookies path)

| Feed | yt-dlp URL |
|------|-----------|
| Subscriptions | `:ytfeed:subscriptions` |
| Home | `:ytfeed:recommended` |
| Liked | `:ytfeed:liked` |
| Playlists | User's channel `/playlists` page |

All calls include `cookiesfrombrowser` in yt-dlp options.

### YouTube Data API v3 Endpoints (OAuth path)

| Feed | API Endpoint |
|------|-------------|
| Subscriptions | `subscriptions.list` + `activities.list` (list channels, then recent uploads) |
| Home | Not available - disabled when using OAuth only |
| Liked | `videos.list` with `myRating=like` |
| Playlists | `playlists.list(mine=true)` + `playlistItems.list` |

### Dual-Provider Logic

Each feed handler checks `settings.youtube_auth_method`:
- `"cookies"`: use yt-dlp with `--cookies-from-browser`
- `"oauth"`: use YouTube Data API v3 via `google-api-python-client`
- Home feed with OAuth only: return an error indicating browser cookies are required

### Pagination

Same offset-based pattern as existing search: 10 results per page, infinite scroll via sentinel intersection observer.

## Settings Changes

### New Fields in `settings.json`

```json
{
  "youtube_auth_method": "cookies | oauth | null",
  "youtube_cookies_browser": "chrome | firefox | chromium | edge | brave | null",
  "youtube_oauth_refresh_token": "...",
  "youtube_oauth_client_id": "...",
  "youtube_oauth_client_secret": "..."
}
```

### Settings Page

New "YouTube Account" section:
- Current auth status display ("Connected via Chrome cookies" or "Connected via Google")
- Browser override dropdown (cookies method)
- OAuth client ID/secret fields (OAuth method)
- Disconnect button

## New Types

### Frontend (`types/index.ts`)

```typescript
interface Playlist {
  playlist_id: string;
  title: string;
  video_count: number;
  thumbnail_url?: string;
}

type FeedView = 'search' | 'subscriptions' | 'home' | 'liked' | 'playlists' | 'playlist-detail';

interface AuthStatus {
  method: 'cookies' | 'oauth';
  detail: string; // e.g. "Chrome" or "tony@gmail.com"
}
```

### Tauri Commands (`commands.rs`)

New commands mirroring each sidecar method:
- `list_subscriptions(offset)`
- `list_home_feed(offset)`
- `list_liked_videos(offset)`
- `list_playlists()`
- `list_playlist_videos(playlist_id, offset)`
- `detect_browser()`
- `connect_cookies(browser?)`
- `connect_oauth(client_id, client_secret, auth_code)`
- `get_auth_status()`

## Error Handling

| Scenario | Message |
|----------|---------|
| Stale cookies | "YouTube cookies expired - log in to YouTube in [Browser] and retry" |
| OAuth token revoked | "Google access revoked - reconnect in Settings" |
| No auth configured | Auth modal prompt |
| Home feed + OAuth only | Sidebar item disabled, tooltip "Home feed requires browser cookies" |
| Empty feed | "No videos found" with contextual hint |
| API quota exceeded | "YouTube API quota reached - try browser cookies instead" |
| Network offline | "No internet connection" |
| yt-dlp rate limited | Backoff and retry (3 attempts), then error |

## New Dependencies

- `google-api-python-client` - YouTube Data API v3 client (OAuth path only)
- `google-auth-oauthlib` - OAuth 2.0 flow handling

## Files Affected

### New Files
- `src/youtube_audio_chunker/youtube_api.py` - YouTube Data API v3 client wrapper
- `src/youtube_audio_chunker/auth.py` - Auth provider abstraction (cookies vs OAuth)
- `gui/src/lib/components/FeedSidebar.svelte` - Sidebar navigation component
- `gui/src/lib/components/FeedView.svelte` - Generic feed result list (reuses search result rendering)
- `gui/src/lib/components/PlaylistGrid.svelte` - Playlist grid view
- `gui/src/lib/components/AuthModal.svelte` - YouTube auth connection modal

### Modified Files
- `gui/src/routes/+page.svelte` - Add sidebar layout wrapper
- `gui/src/routes/settings/+page.svelte` - Add YouTube Account section
- `gui/src/lib/stores/library.svelte.ts` - Add feed fetch methods
- `gui/src/lib/types/index.ts` - Add Playlist, FeedView, AuthStatus types
- `gui/src/lib/backend.ts` - Add new backend call wrappers (if needed)
- `gui/src-tauri/src/commands.rs` - Add new Tauri commands
- `gui/src-tauri/src/lib.rs` - Register new commands
- `src/youtube_audio_chunker/sidecar.py` - Add feed handler methods
- `src/youtube_audio_chunker/downloader.py` - Add feed extraction functions (cookies path)
- `src/youtube_audio_chunker/settings.py` - Add auth-related settings fields
