# Two-Column Search Layout

## Problem

The search bar and results sit above the library in a single column. When search results appear, they push the library down, preventing the user from seeing both at once. On wide screens, horizontal space goes unused.

## Design

An on-demand two-column layout that activates only when search results are present.

### Default State (no search results)

Single centered column with max-width 700px - identical to the current layout. Search form sits above the library (queue + downloaded + device-only lists). No changes from current behavior.

### Active Search State (results showing)

When search results appear, the layout widens and splits into two equal columns:

- **Left column:** Search form + search results (scrolls independently)
- **Right column:** Library - queue, downloaded, device-only lists (scrolls independently)

Both columns are equal width (50/50 split).

### Transition Triggers

- **Single to two-column:** Search results are returned and displayed
- **Two-column to single:** User clicks the close (X) button on the search results panel

No auto-dismiss on adding items. Close button is the only way to return to single column.

### Responsive Behavior

When the viewport is too narrow to fit two comfortable columns side by side, fall back to the current stacked single-column layout. The breakpoint should be determined by the minimum comfortable column width (roughly 350px per column, so ~750px viewport minimum for two-column mode).

## Components Affected

- `+page.svelte` - Dashboard layout needs conditional two-column CSS
- `AddEpisodeForm.svelte` - Needs to expose whether search results are visible (may already do this via its results panel rendering)
- `app.css` - May need new CSS custom properties for the wider max-width

## Out of Scope

- Resizable column divider
- Remembering column preference across sessions
- Different column ratios
- Animation/transition effects between states (can be added later)
