# Graph Data API - Development Spec

## Goal
Provide one endpoint that returns graph visualization data (nodes and edges) for the analytics UI using a hybrid retrieval pipeline:
1. DuckDB applies all filter parameters and preselects candidate title/person IDs.
2. Neo4j expands graph relationships constrained to those candidate IDs with one-level neighborhood expansion around anchors.

This keeps filter semantics aligned with the relational pipeline while reducing Neo4j query scope.

## Endpoint
- Method: GET
- Path: `/query/graph-data`

## Query Parameters
All parameters are optional and mirror `/query/items-found`.

| Parameter | Type | Description |
|---|---|---|
| `titleId` | string | Anchor graph to a specific title (`tconst`) |
| `nameId` | string | Anchor graph to a specific person (`nconst`) |
| `titleType` | string | Filter by title type (e.g., `movie`, `tvSeries`) |
| `genre` | string | Filter by genre token (e.g., `Drama`) |
| `ratingRangeFrom` | float | Lower bound of `averageRating` (inclusive) |
| `ratingRangeTo` | float | Upper bound of `averageRating` (inclusive) |
| `releaseYearFrom` | integer | Lower bound of `startYear` (inclusive) |
| `releaseYearTo` | integer | Upper bound of `startYear` (inclusive) |
| `topRated` | boolean | Include only titles from top-rated source set (default: `false`) |
| `mostPopular` | boolean | Include only titles from most-popular source set (default: `false`) |

These parameters must be applied in DuckDB preselection before any Neo4j expansion is executed.

### Validation Rules
1. If both `ratingRangeFrom` and `ratingRangeTo` are provided, `ratingRangeFrom <= ratingRangeTo` must hold.
2. If both `releaseYearFrom` and `releaseYearTo` are provided, `releaseYearFrom <= releaseYearTo` must hold.
3. `ratingRangeFrom` and `ratingRangeTo` must be in the range `1.0..10.0`.
4. Invalid range combinations return `422`.

Examples:
- `/query/graph-data`
- `/query/graph-data?topRated=true&genre=Drama`
- `/query/graph-data?ratingRangeFrom=7.0&ratingRangeTo=9.0&releaseYearFrom=2000&releaseYearTo=2020`
- `/query/graph-data?nameId=nm0000209&mostPopular=true`

## Response Shape
```json
{
	"nodes": [
		{
			"id": "tt0111161",
			"type": "Title",
			"label": "The Shawshank Redemption",
			"titleType": "movie",
			"genres": ["Drama"],
			"startYear": 1994,
			"averageRating": 9.3,
			"numVotes": 2900000,
			"isAnchor": false,
			"score": 0.992
		},
		{
			"id": "nm0000209",
			"type": "Person",
			"label": "Tim Robbins",
			"primaryProfession": ["actor", "producer"],
			"birthYear": 1958,
			"isAnchor": true,
			"score": 0.871
		}
	],
	"edges": [
		{
			"id": "nm0000209->tt0111161:ACTED_IN",
			"source": "nm0000209",
			"target": "tt0111161",
			"type": "ACTED_IN",
			"category": "actor",
			"job": null,
			"characters": ["Andy Dufresne"],
			"score": 0.945
		}
	],
	"meta": {
		"maxNodes": 1000,
		"maxEdges": 3000,
		"returnedNodes": 742,
		"returnedEdges": 1984,
		"truncated": false
	}
}
```

## Data Rules

### 0. Hybrid retrieval stages
- Retrieval is two-stage and ordered:
	1. DuckDB preselection stage.
	2. Neo4j constrained expansion stage.
- Neo4j must not run an unconstrained full-graph query for this endpoint.

### 1. DuckDB preselection and source-set alignment
- DuckDB preselection applies the same source relation mapping as other query endpoints:
	- `(false, false)` -> `all_titles_ratings`
	- `(true, false)` -> `top_rated_titles`
	- `(false, true)` -> `most_popular_titles`
	- `(true, true)` -> `top_rated_popular_titles`
- Apply all active query filters in DuckDB preselection:
	- `titleId`, `nameId`, `titleType`, `genre`
	- `ratingRangeFrom`, `ratingRangeTo`
	- `releaseYearFrom`, `releaseYearTo`
	- `topRated`, `mostPopular`
- Preselection output:
	- Candidate title IDs (`tconst`) with a hard cap of `1000` IDs.
	- Candidate person IDs (`nconst`) with a hard cap of `1000` IDs.
- Anchor filtering semantics:
	- `titleId` and `nameId` remain filter-bound inputs and do not bypass source-set/title filters.
	- If filters produce no title candidates, return an empty graph response with valid `meta`.
	- In non-anchor mode (no `titleId` and no `nameId`), empty person candidates also return an empty graph response.

### 2. Neo4j constrained expansion
- Neo4j queries must be constrained by DuckDB candidate ID sets.
- Expansion is anchor-aware and one-level deep:
	- `nameId` mode: anchor person -> candidate titles connected to anchor -> all core-category collaborators connected to those titles.
	- `titleId` mode: anchor title -> core-category collaborators on anchor title -> candidate titles connected to those collaborators -> all core-category collaborators on those titles.
	- Non-anchor mode: operate within candidate titles/persons and relationships connecting them.
- Collaborator inclusion rule:
	- For anchor expansion modes, collaborator persons connected to included titles are included even when they are not in DuckDB person candidate IDs.
- Always include only core person categories:
	- `actor`
	- `actress`
	- `director`
	- `writer`
	- `composer`
	- `producer`
- Category enforcement is mandatory server-side and is not configurable in v1.

### 3. Returned graph entities
- Nodes:
	- `Title` nodes use `tconst` as `id`.
	- `Person` nodes use `nconst` as `id`.
- Edges:
	- Directed from person to title.
	- `type` is Neo4j relationship type (for example: `ACTED_IN`, `DIRECTED`, `WROTE`, `PRODUCED`, `COMPOSED`).
	- Preserve relationship properties: `category`, `job`, `characters`.

### 4. Relevance scoring and deterministic ordering
- Compute relevance score for deterministic truncation.
- Required ordering before truncation:
	1. Descending score.
	2. Relationship priority for ties: `DIRECTED`, `PRODUCED`, `WROTE`, `COMPOSED`, `ACTED_IN`.
	3. Stable lexical tie-breaker by node/edge ID.
- Recommended score inputs:
	- Title: `averageRating`, `numVotes`, source-set membership.
	- Person: degree within filtered subgraph, count of high-score connected titles.
	- Edge: relationship priority and endpoint scores.

### 5. Hard limits and truncation
- Return at most `1000` nodes and `3000` edges.
- `meta.returnedNodes` must never exceed `1000`.
- Truncation must be deterministic for identical inputs.
- Trim edges first by ordering if edge count exceeds limit.
- Then trim nodes by ordering while removing orphaned edges.
- Response must set `meta.truncated=true` when any limit is applied.

### 6. Performance constraints
- Query must execute within a reasonable time for interactive UI use.
- Bound DuckDB candidate extraction to fixed caps (1000 titles + 1000 persons).
- Prefer Cypher-side filtering and limiting over in-memory post-processing.
- Avoid full graph scans.
- Keep database round-trips minimal (small bounded query set).

## N-Tier Structure

| Layer | Responsibility |
|---|---|
| `endpoints/` | Parse and validate query params; apply per-route rate limit; call service |
| `services/` | Orchestrate staged retrieval (DuckDB preselection -> Neo4j constrained expansion), apply scoring/truncation pipeline, assemble response |
| `repositories/` | DuckDB candidate-ID queries + Neo4j Cypher statements, parameter binding, result hydration |
| `schemas/` | Query model, node/edge DTOs, response model with `meta` |

### DuckDB requirements
- Reuse source relation selection and filter-clause semantics aligned with `/query/items-found`.
- Candidate preselection must remain deterministic for identical inputs.

### Neo4j connection requirements
- Use the same environment variables used by seeding:
	- `NEO4J_URI`
	- `NEO4J_USER`
	- `NEO4J_PASSWORD`
- Use the official `neo4j` Python package.
- Integrate in the existing FastAPI app and follow current request/response patterns.

## Rate Limiting
- Enforce `1 request / second / IP` for `/query/graph-data`.
- Exceeding the limit should return `429 Too Many Requests`.

## Error Behavior
- Invalid ranges or invalid value types -> `422`.
- Upstream Neo4j availability/query failures -> `503` with safe error message.
- Rate-limit violations -> `429`.

## Non-Goals
- No graph pagination in v1.
- No client-configurable category set in v1.
- No streaming or chunked graph delivery in v1.

## Acceptance Criteria
1. Endpoint `/query/graph-data` exists and accepts the same filter parameters as `/query/items-found`.
2. DuckDB preselection applies all query parameters and source-set mapping before Neo4j is queried.
3. DuckDB candidate output is capped at 1000 title IDs and 1000 person IDs.
4. Neo4j expansion is constrained by candidate IDs and returns rich `nodes` and `edges` plus `meta`.
5. `nameId` anchor mode returns one-level expanded neighborhoods: anchor person's filtered titles plus all core-category collaborators on those titles.
6. `titleId` anchor mode returns one-level expanded neighborhoods: anchor-title collaborators plus their filtered titles and collaborators on those titles.
7. In anchor modes, collaborators connected to included titles are included even when not in DuckDB person candidate IDs.
8. In non-anchor mode, expansion remains constrained by both candidate title and candidate person sets.
9. Only core categories (`actor`, `actress`, `director`, `writer`, `composer`, `producer`) are present.
10. Hard caps of 1000 nodes and 3000 edges are always respected, and `meta.returnedNodes <= 1000` always holds.
11. Truncation is deterministic and signaled via `meta.truncated`.
12. Anchor behavior remains filter-bound (no bypass of active filters/source-set constraints).
13. Endpoint is rate-limited to 1 request per second per IP.
14. Validation and operational errors return the documented HTTP status codes.
