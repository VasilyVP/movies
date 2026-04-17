# Items Found API - Development Spec

## Goal
Provide one endpoint that returns the total count of titles and persons matching a given set of filters.

## Endpoint
- Method: GET
- Path: `/query/items-found`

## Query Parameters
All parameters are optional.

| Parameter | Type | Description |
|---|---|---|
| `titleId` | string | Filter to a specific title (`tconst`) |
| `nameId` | string | Filter to titles associated with a specific person (`nconst`) |
| `titleType` | string | Filter by title type (e.g., `movie`, `tvSeries`) |
| `genre` | string | Filter by genre token (e.g., `Drama`) |
| `ratingRangeFrom` | float | Lower bound of `averageRating` (inclusive) |
| `ratingRangeTo` | float | Upper bound of `averageRating` (inclusive) |
| `releaseYearFrom` | integer | Lower bound of `startYear` (inclusive) |
| `releaseYearTo` | integer | Upper bound of `startYear` (inclusive) |
| `topRated` | boolean | Use `top_rated_titles` view as source (default: `false`) |
| `mostPopular` | boolean | Use `most_popular_titles` view as source (default: `false`) |

### Validation Rules
1. If both `ratingRangeFrom` and `ratingRangeTo` are provided, `ratingRangeFrom <= ratingRangeTo` must hold.
2. If both `releaseYearFrom` and `releaseYearTo` are provided, `releaseYearFrom <= releaseYearTo` must hold.
3. `ratingRangeFrom` and `ratingRangeTo` must be in the range `1.0..10.0`.
4. Invalid range combinations return `422`.

Examples:
- `/query/items-found`
- `/query/items-found?topRated=true&genre=Drama`
- `/query/items-found?ratingRangeFrom=7.0&ratingRangeTo=9.0&releaseYearFrom=2000&releaseYearTo=2020`
- `/query/items-found?nameId=nm0000209&topRated=true`
- `/query/items-found?titleType=movie&mostPopular=true`

## Response Shape
```json
{
  "totalTitles": 4821,
  "totalPersons": 12043
}
```

## Data Rules

### 0. Source relation selection
- If both flags are `false`, use `all_titles_ratings` view.
- If `topRated=true` and `mostPopular=false`, use `top_rated_titles` view.
- If `topRated=false` and `mostPopular=true`, use `most_popular_titles` view.
- If `topRated=true` and `mostPopular=true`, use `top_rated_popular_titles` view.
- All views already include `averageRating` and `numVotes` columns (rating data is embedded in every view by the startup initialisation).
- The selected source relation is applied consistently to both the titles count and the persons count.

### 1. Titles count
Count distinct `tconst` values from the selected view satisfying all active filters:

- `titleId` → `tb.tconst = ?`
- `nameId` → title must appear in `title_principals` for the given `nconst`
- `titleType` → `lower(tb.titleType) = lower(?)`
- `genre` → title's `genres` column contains the token (case-insensitive, comma-split)
- `ratingRangeFrom` → `tb.averageRating >= ?` (column is present in all source views)
- `ratingRangeTo` → `tb.averageRating <= ?` (column is present in all source views)
- `releaseYearFrom` → `CAST(tb.startYear AS INTEGER) >= ?`
- `releaseYearTo` → `CAST(tb.startYear AS INTEGER) <= ?`

```sql
SELECT COUNT(DISTINCT tb.tconst) AS total
FROM {source_table} tb
[JOIN title_principals tp ON tb.tconst = tp.tconst  -- only when nameId is set]
WHERE <active filter clauses>
```

### 2. Persons count
Count distinct `nconst` values from `name_unique` where the person is linked (via `title_principals`) to at least one title that satisfies all active filters:

```sql
SELECT COUNT(DISTINCT nu.nconst) AS total
FROM name_unique nu
JOIN title_principals tp ON nu.nconst = tp.nconst
JOIN {source_table} tb ON tp.tconst = tb.tconst
WHERE <active filter clauses>
```

- When `nameId` is provided, restrict to `nu.nconst = ?`.
- Apply the same title-derived filter clauses as in the titles count.

### 3. Parallelism
Run the titles count query and the persons count query concurrently using `ThreadPoolExecutor(max_workers=2)` in the service layer.

## N-Tier Structure

| Layer | Responsibility |
|---|---|
| `endpoints/` | Parse and validate query parameters; call service |
| `services/` | Resolve source relation; fan out two count queries in parallel; assemble response |
| `repositories/` | SQL templates with `{source_table}` placeholder; `_resolve_source_relation()` helper |
| `schemas/` | `ItemsFoundParams` (query model), `ItemsFoundResponse` (response model) |

### Source relation resolution
Reuse the same `_resolve_source_relation(top_rated, most_popular) -> SourceRelation` pattern used in other query services:
- `(False, False)` → `"all_titles_ratings"`
- `(True, False)` → `"top_rated_titles"`
- `(False, True)` → `"most_popular_titles"`
- `(True, True)` → `"top_rated_popular_titles"`

## Error Behavior
- Invalid range combinations (`ratingRangeFrom > ratingRangeTo`, `releaseYearFrom > releaseYearTo`) → `422`.
- Rating values outside `1.0..10.0` → `422`.
- Unknown or invalid parameter values that cannot be coerced → `422`.

## Non-Goals
- This endpoint does not return title or person records, only counts.
- No pagination or result limit applies.
- No caching is required in v1.
