# Pattern: Custom HTTP Hook (TanStack Query)

## Goal

Provide one reusable hook for a feature endpoint so component code stays focused on UI while fetch, cache, and error logic remain centralized.

## Use When

- A component needs HTTP data with loading and error states.
- The same endpoint behavior may be reused in multiple components.
- Query parameter changes should trigger refetch automatically.

## Avoid When

- The request is one-off and has no UI state impact.
- The call must be done only as an explicit user action (use mutation pattern instead).

## Standard Contract

### Hook Name

Use the format: use<FeatureName>

Examples:

- useFilterOptions
- useTitleDetails

### Inputs

- params object with all query parameters needed for endpoint selection.
- optional enabled flag for conditional execution.

### Returns

At minimum return:

- data
- isLoading
- isFetching
- error
- refetch (optional for manual refresh action)

## Query Key Pattern

Use a stable key with namespace + endpoint purpose + params object.

Example key shape:

- ["query", "filter-options", { topRated, mostPopular }]

Rules:

- Include every request-shaping parameter in the key.
- Keep key order deterministic.
- Do not use one global key for multiple parameter combinations.

## Fetch Function Pattern

- Keep fetcher logic close to the hook or in a shared api client module.
- Build URL search params from hook inputs.
- Throw on non-OK response so TanStack Query handles error state.

## Suggested TypeScript Shape

```ts
import { useQuery } from "@tanstack/react-query";

type HookParams = {
  topRated: boolean;
  mostPopular: boolean;
  enabled?: boolean;
};

type FilterOptions = {
  genres: string[];
  titleTypes: Array<{ value: string; label: string }>;
  yearRange: { min: number; max: number };
  ratingRange: { min: number; max: number };
};

async function fetchFilterOptions(params: Omit<HookParams, "enabled">): Promise<FilterOptions> {
  const search = new URLSearchParams({
    topRated: String(params.topRated),
    mostPopular: String(params.mostPopular),
  });

  const response = await fetch(`/query/filter-options?${search.toString()}`);

  if (!response.ok) {
    throw new Error("Failed to fetch filter options");
  }

  return (await response.json()) as FilterOptions;
}

export function useFilterOptions(params: HookParams) {
  const { enabled = true, ...queryParams } = params;

  return useQuery({
    queryKey: ["query", "filter-options", queryParams],
    queryFn: () => fetchFilterOptions(queryParams),
    enabled,
  });
}
```

## UI Consumption Pattern

Component should:

- call the custom hook with current state-derived params.
- render loading state when isLoading is true and no data exists.
- render inline error when error exists.
- render stale data while isFetching updates in background when appropriate.

## State Sync Pattern

If hook data controls valid options:

- preserve selected values still present in returned options.
- remove only invalid selections after refresh.
- keep this state reconciliation at upper-level state owner component.

## Acceptance Criteria Template

1. Hook fetches data on first mount when enabled is true.
2. Changing any request-shaping input creates or uses the matching query key.
3. Previously fetched key combinations return cached data on revisit.
4. Non-OK responses surface through hook error state.
5. Component using the hook renders loading, success, and error states correctly.
6. If option-driven, stale selections are pruned and valid selections are preserved.

## Project Notes

- Use Bun for dependency and script operations in this repository.
- Prefer shared typed response models for endpoint payloads.
- Keep hook files small and feature-focused.
