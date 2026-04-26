# Graph Visualization - Front-End Spec

## Goal

Implement an interactive graph visualization experience in Analytics that renders nodes and edges from `/query/graph-data`, while respecting existing filter state and the result-size guardrail already provided by Items Found.

This spec defines v1 behavior only.

## Scope and Decisions (v1)

- Graph data fetch is triggered only by clicking Show graph.
- Clicking a node selects and highlights it, then shows inline node details.
- Front-end graph rendering uses the full node and edge sets returned by `/query/graph-data`.
- Layout switching is in scope for v1.

## Files

| File | Action |
|------|--------|
| `src/hooks/useGraphData.ts` | Create - TanStack Query hook for `/query/graph-data` |
| `src/components/features/GraphVisualization.tsx` | Modify - replace placeholder canvas with NVL graph and interactive controls |
| `src/components/features/FilterPanel.tsx` | Modify - wire Show graph action to request graph fetch |
| `src/routes/Analytics/Analytics.tsx` | Modify - own graph-request trigger state and pass graph props to children |

## API Contract Reference

Back-end behavior is already specified in `specs/back-end/graph_data.md`.

Front-end must treat the response as:

```ts
type GraphNode = {
	id: string;
	type: "Title" | "Person";
	label: string;
	isAnchor?: boolean;
	score?: number;
	titleType?: string;
	genres?: string[];
	startYear?: number;
	averageRating?: number;
	numVotes?: number;
	primaryProfession?: string[];
	birthYear?: number;
};

type GraphEdge = {
	id: string;
	source: string;
	target: string;
	type: string;
	category?: string | null;
	job?: string | null;
	characters?: string[] | null;
	score?: number;
};

type GraphMeta = {
	maxNodes: number;
	maxEdges: number;
	returnedNodes: number;
	returnedEdges: number;
	truncated: boolean;
};

type GraphDataResponse = {
	nodes: GraphNode[];
	edges: GraphEdge[];
	meta: GraphMeta;
};
```

## Hook: `useGraphData`

Follow the project hook pattern used by `useFilterOptions`, `useItemsFound`, and `useSearch`.

### Inputs

```ts
type GraphQueryParams = {
	titleId?: string | null;
	nameId?: string | null;
	titleType?: string | null;
	genre?: string | null;
	ratingRangeFrom?: number | null;
	ratingRangeTo?: number | null;
	releaseYearFrom?: number | null;
	releaseYearTo?: number | null;
	topRated: boolean;
	mostPopular: boolean;
};
```

### Query Key

- `queryKey`: `['query', 'graph-data', params, requestToken]`
- Include all request-shaping params in `params`.
- `requestToken` is a monotonically increasing integer owned by `Analytics` and incremented only when Show graph is clicked.

### Fetch Trigger Model

- `enabled` must depend on a graph request being made (for example, `requestToken > 0`).
- Changing filters alone does not trigger graph fetch.
- Clicking Show graph triggers a new fetch for the latest filters by incrementing `requestToken`.

### Return Shape

Hook returns at least:

- `data: GraphDataResponse | undefined`
- `isLoading: boolean`
- `isFetching: boolean`
- `isError: boolean`
- `error: Error | null`
- `refetch: () => Promise<unknown>`

## Analytics Integration

`Analytics` remains the owner of canonical filter state and adds graph-request state.

Required integration behavior:

1. Maintain `graphRequestToken` in route state.
2. Pass Show graph handler to `FilterPanel`.
3. Build graph query params from current filter state and selected search result.
4. Call `useGraphData(params, graphRequestToken)` in `Analytics`.
5. Pass graph query state into `GraphVisualization`.

Anchor mapping guidance:

- If selected search item is a title, map to `titleId`.
- If selected search item is a person, map to `nameId`.
- If no selected item exists, omit both anchor params.

## FilterPanel Integration

Show graph remains user-initiated and guarded by Items Found threshold.

Rules:

1. Keep current threshold guard (`total <= 1000`) for enabling Show graph.
2. If disabled, do not dispatch graph fetch trigger.
3. If enabled and clicked, invoke parent callback to increment `graphRequestToken`.
4. Existing debounced Items Found fetch behavior remains unchanged.

## Component: `GraphVisualization`

### Responsibilities

- Render graph canvas using:
	- `@neo4j-nvl/react`
	- `@neo4j-nvl/base`
	- `@neo4j-nvl/interaction-handlers`
- Render toolbar controls (layout, relationship filter, zoom buttons).
- Render stats footer using returned graph data.
- Manage selected node state and inline details panel.

### Props

```ts
type GraphVisualizationProps = {
	data: GraphDataResponse | undefined;
	isLoading: boolean;
	isFetching: boolean;
	isError: boolean;
	error: Error | null;
	onRetry: () => void;
};
```

### Internal UI State

```ts
type LayoutMode = "force" | "hierarchical" | "circular" | "radial";
```

- `selectedNodeId: string | null`
- `layoutMode: LayoutMode`

### Node Interaction

- Node click selects node.
- Selected node gets visual highlight.
- Inline details section displays selected node fields:
	- Shared: `id`, `label`, `type`, `score`, `isAnchor`
	- Title fields when present: `titleType`, `genres`, `startYear`, `averageRating`, `numVotes`
	- Person fields when present: `primaryProfession`, `birthYear`
- Clicking empty canvas clears selection.

### Drag and Zoom Interaction

- Nodes are draggable.
- Zoom buttons (`+`, `-`, reset) must be wired to NVL view controls.
- Drag and zoom interactions must not clear selected node by default.

### Layout Switching

- Layout selector applies chosen mode to current visible graph data.
- Mode switch is immediate and does not re-fetch data.
- Selection remains when possible (if selected node stays visible).

## UI State Matrix

| State | Condition | Required Rendering |
|------|-----------|--------------------|
| Idle | Show graph never clicked | Placeholder prompt: "Adjust filters and click Show graph" |
| Loading | `isLoading` | Loading skeleton/spinner in canvas area |
| Refreshing | `isFetching && !!data` | Keep graph visible with subtle loading indicator |
| Error | `isError` | Error panel with retry action |
| Empty | `data` exists and either nodes or edges is empty | Empty-state panel: "No graph data for current filters" |
| Success | Non-empty graph | Full interactive graph + toolbar + stats + optional selection details |

Truncation rule:

- When `data.meta.truncated === true`, show a visible warning badge in the graph header/footer with returned counts.

## Stats Footer Rules

Display actual values from the rendered response and local selection:

- Nodes: rendered node count from the `/query/graph-data` response.
- Edges: rendered edge count from the `/query/graph-data` response.
- Selected: selected node label or `None`.
- Optional: show returned counts from `meta.returnedNodes` and `meta.returnedEdges` for truncation reference.

## Error Handling

- Preserve safe user-facing message.
- For HTTP 503, show service-unavailable wording and retry option.
- For HTTP 422, show invalid-filter wording.
- Avoid exposing stack traces or raw backend internals.

## Accessibility

1. Toolbar controls must have accessible labels.
2. Selected-node details must be reachable by keyboard after node selection.
3. Error and truncation notices must be announced via semantic status regions.
4. Color contrast in graph legends/badges must remain readable on existing dark surface.

## Non-Goals (v1)

- No auto-fetch on every filter change.
- No backend-driven relationship filter parameter.
- No pagination/streaming graph chunks.
- No cross-page navigation on node click.

## Acceptance Criteria

1. Graph request is sent only after Show graph is clicked.
2. Changing filters without clicking Show graph does not trigger graph fetch.
3. Show graph remains disabled when Items Found exceeds 1000 and no graph request is triggered in that state.
4. Successful fetch renders graph with non-zero stats when data contains nodes and edges.
5. Layout selector updates arrangement without additional API requests.
6. Relationship filter applies purely client-side and updates visible nodes/edges immediately.
7. Clicking a node highlights it and shows inline node details.
8. Dragging nodes and using zoom controls work without losing current selection.
9. `meta.truncated=true` displays a visible truncation warning with returned counts.
10. Error state displays a retry action that re-attempts the same graph request.
11. Empty data response renders a dedicated empty-state message.
12. All required graph controls are keyboard-focusable with accessible labels.