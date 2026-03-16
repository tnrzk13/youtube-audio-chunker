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

No auto-dismiss on adding items. Close button is the only way to return to single column. Closing from channel-browse view also collapses to single column (same as dismissing search results).

### Responsive Behavior

When the viewport is too narrow to fit two comfortable columns side by side, fall back to the current stacked single-column layout. The breakpoint should be determined by the minimum comfortable column width (roughly 350px per column, so ~750px viewport minimum for two-column mode).

## Implementation Details

### Surfacing search state to the page

`AddEpisodeForm` exposes a bindable `hasResults` prop (`$bindable()`) so `+page.svelte` can read whether search results (or channel videos) are currently displayed. This drives the layout class toggle on `.dashboard`.

### Component structure stays the same

`AddEpisodeForm` continues to own both the search form and the results panel - no extraction needed. In two-column mode, the left column is the entire `AddEpisodeForm` component and the right column is `.episode-scroll`. The split happens at the `+page.svelte` level with a CSS grid or flex wrapper.

### CSS changes

- **`+page.svelte`:** `.dashboard` gets a conditional class (e.g. `.dashboard.two-column`) that switches from single centered column to a two-column flex/grid layout. The `> :global(*)` max-width 700px rule is overridden in two-column mode to allow the wider container.
- **`AddEpisodeForm.svelte`:** The existing `max-height: 300px` on `.search-results` is removed or overridden in two-column mode so results fill the available column height.
- **Toolbar:** Stays at its current width/behavior. It already uses responsive padding (`max(1rem, calc((100% - 700px) / 2))`) and does not need to widen with the dashboard since it's a separate element.

## Components Affected

- `+page.svelte` - Dashboard layout conditional two-column CSS, reads `hasResults` from AddEpisodeForm
- `AddEpisodeForm.svelte` - Exposes bindable `hasResults` prop, adjusts search results max-height in two-column mode
- `app.css` - May need new CSS custom properties for the wider max-width

## Out of Scope

- Resizable column divider
- Remembering column preference across sessions
- Different column ratios
- Animation/transition effects between states (can be added later)
- Tauri minimum window size changes
- Focus management during layout transition
