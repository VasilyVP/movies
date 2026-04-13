# Filter Params Front-End Specification

## Overview

This specification defines how the Analytics page loads, stores, and applies filter options returned by the back-end filter options endpoint.
It standardizes ownership of filter state, options fetching behavior, caching strategy, and UI behavior for loading and error states.

## Goal

Provide a predictable filter-options flow so that:

- FilterPanel always renders with options based on current top rated and most popular toggles.
- Filter state is managed from one source of truth in Analytics.
- Data fetching and caching behavior is encapsulated and reusable.

## Scope

Included:

- Front-end fetching of filter options from /query/filter-options.
- Refetch behavior when top rated or most popular toggles change.
- Shared filter-state ownership in Analytics via useImmer.
- useFilterOptions custom hook contract and TanStack Query usage.
- FilterPanel loading and error behavior.

Excluded:

- Back-end endpoint implementation or schema changes.
- Title query execution behavior after filters are submitted.
- URL persistence or local-storage persistence of filter state.

## Data Source

- Endpoint: GET /query/filter-options
- Query parameters:
	- topRated: boolean
	- mostPopular: boolean

The front-end must pass the current toggle values to the endpoint on each relevant fetch.

## Component and State Architecture

### Analytics Component

Analytics is the single owner of filter state.

Requirements:

- Keep all filter values in one state object in Analytics.
- Use useImmer for filter state updates.
- Hold both:
	- selected filter values (user selections)
	- toggle values (topRated, mostPopular)
- Keep Analytics focused on state ownership and composition; avoid placing filter field/toggle update handlers there.

### FilterPanel Component

FilterPanel is a controlled UI layer.

Requirements:

- Receives selected filter values and a state setter from Analytics.
- Uses useFilterOptions to obtain available options.
- Renders options from hook data only.
- Does not own canonical filter state.
- May own filter interaction and transition logic (field changes, toggle changes, and option-refresh reconciliation) as long as updates are applied through the Analytics-owned state object.

## Hook Specification: useFilterOptions

The useFilterOptions hook encapsulates filter-options loading and caching.

### Inputs

- topRated: boolean
- mostPopular: boolean

### Query Key

Use a stable TanStack Query key that includes both flags as part of key state.

Behavior requirement:

- Each topRated and mostPopular combination is cached independently.
- The four valid combinations map to four distinct cache entries.

### Returns

The hook must provide at minimum:

- data: filter options payload (or undefined before first successful load)
- isLoading: true during initial load for a given cache entry
- isFetching: true during background refresh or key change fetch
- error: fetch error value when request fails

The hook may expose additional TanStack Query metadata if needed by UI.

### Fetch Triggers

- Fetch on FilterPanel mount for the active toggle combination.
- Refetch automatically when either topRated or mostPopular changes.
- Reuse cached data when returning to a previously fetched toggle combination.

## UI Behavior

### Initial Load

- While no successful data exists for the active key, show loading state in FilterPanel.
- Populate controls only after data is available.

### Toggle Change

- When topRated or mostPopular changes, request options for the new combination.
- UI may continue showing previously displayed options while fetch is in flight.
- Once new options arrive, update rendered options to the new dataset.

### Error Handling

- On request failure, show an inline error state in FilterPanel.
- Keep last successful cached options visible when available.
- If no successful data exists yet for that key, render an empty-options fallback plus error state.

## Selected Filter Persistence Rules

When options are refreshed due to toggle changes:

- Preserve currently selected values that still exist in refreshed options.
- Remove only selected values that are no longer valid in refreshed options.
- Keep unaffected fields unchanged.

This prevents unnecessary reset while preserving validity.

Implementation nuance:

- The reconciliation logic that enforces these rules may live inside FilterPanel for cohesion with fetching behavior.
- Analytics remains the canonical state owner even when reconciliation is triggered from FilterPanel.

## TanStack Query Requirements

- useFilterOptions must be implemented using TanStack Query.
- Query function must call /query/filter-options with current toggle values.
- Caching behavior must be key-driven, not global overwrite.
- Hook consumers must not perform manual duplicate fetch logic outside TanStack Query.

## Integration Points

- front-end/src/routes/Analytics/Analytics.tsx
	- Owns filter state and toggles using useImmer.
	- Passes current filters and state setter to FilterPanel.
- front-end/src/components/features/FilterPanel.tsx
	- Consumes useFilterOptions and renders filter UI states.
	- Handles filter interaction and reconciliation logic, writing changes through the setter from Analytics.
- front-end/src (shared hooks area)
	- Contains useFilterOptions implementation.

## Acceptance Criteria

1. FilterPanel loads filter options from /query/filter-options on first render.
2. Changing topRated triggers options refetch for the new toggle state.
3. Changing mostPopular triggers options refetch for the new toggle state.
4. Switching between toggle combinations reuses previously cached results for combinations already fetched.
5. Filter state is owned by Analytics in one useImmer-managed state object.
6. useFilterOptions encapsulates all filter-options network access and TanStack Query integration.
7. On fetch failure with prior successful data, FilterPanel shows inline error and keeps last successful options visible.
8. On fetch failure without prior successful data, FilterPanel shows inline error and an empty-options fallback.
9. On toggle change, selected filters persist when still valid in refreshed options.
10. On toggle change, only invalid selected values are removed from state.

## Out of Scope

- Defining back-end SQL or data-source rules for filter option generation.
- Defining analytics result-list query behavior.
- Defining persisted filter sessions across page reloads.
