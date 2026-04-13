# Movies Project Guidelines

## Architecture

Full-stack app: IMDB data pipeline feeding a relational store, graph store, and REST API served to a React front-end.

```
IMDB TSV.GZ → Parquet (back-end/data/) → DuckDB (imdb.duckdb) → Neo4j graph
                                                  ↓
                                    FastAPI (back-end/) → React + Vite (front-end/)
```

- **DuckDB** — relational queries over Parquet files; single-file `back-end/data/imdb.duckdb`
- **Neo4j** — graph traversals; runs in Docker (browser: `localhost:7474`, bolt: `localhost:7687`)
- **FastAPI** — REST API (`back-end/app/`); N-tier: `endpoints → services → repositories → database`; served by Granian
- **React** — SPA (`front-end/src/`); React 19 + Vite 8 + TypeScript strict + Tailwind 4 + shadcn/ui
- **Scripts** — ETL/pipeline logic in `scripts/`

## Data Schema

See [specs/data_seeding/imdb_seed.md](../specs/data_seeding/imdb_seed.md) and [specs/data_seeding/neo4j_seed.md](../specs/data_seeding/neo4j_seed.md) for full pipeline details.

### DuckDB / Parquet Tables

| Table | Key Columns |
|-------|-------------|
| `title_basics` | `tconst`, `titleType`, `primaryTitle`, `originalTitle`, `isAdult`, `startYear`, `endYear`, `runtimeMinutes`, `genres` |
| `title_principals` | `tconst`, `nconst`, `category`, `job`, `characters` |
| `title_ratings` | `tconst`, `averageRating`, `numVotes` |
| `name_unique` | `nconst`, `primaryName`, `birthYear`, `deathYear`, `primaryProfession`, `knownForTitles` |

`name_unique` is filtered from `name.basics` — only persons linked to at least one title in `title_principals`. IMDB uses `\N` as a null sentinel; it's converted to SQL `NULL` during ingestion.

### Neo4j Graph Schema

**Nodes**: `Person` (PK: `nconst`), `Title` (PK: `tconst`, includes rating columns)

**Relationships** (direction: `Person → Title`), derived from `title_principals.category`:
`ACTED_IN`, `DIRECTED`, `WROTE`, `PRODUCED`, `COMPOSED`, `EDITED`, `SHOT`, `DESIGNED`, `CAST`, `APPEARED_IN`

Relationship properties: `category`, `job`, `characters` (all nullable). Unrecognised categories are normalised to `UPPER_SNAKE_CASE`.

## Build and Test

```bash
# Infrastructure
make install       # Start Neo4j container (docker compose up -d)
make start         # Resume stopped containers (data preserved)
make stop          # Pause containers (data preserved)
make teardown      # Remove containers and networks (volumes kept)
make reset         # Full wipe: containers, networks, volumes, all data files
make status        # Check running containers
make logs          # Tail logs

# Data pipeline
make seed          # Full pipeline: download IMDB → Parquet → DuckDB → Neo4j (~30 min)
make seed-sample   # Pipeline with 1,000 titles — use this for dev/testing

# Development servers (requires concurrently)
make dev           # Start Neo4j + FastAPI dev server + Vite dev server concurrently
```

Run individually:
```bash
uv run python scripts/imdb_seed.py
uv run python scripts/neo4j_seed.py [--limit N]
uv run --directory back-end fastapi dev app/main.py  # back-end only

# Front-end
cd front-end && bun run dev    # Vite dev server on port 3000
cd front-end && bun run build

# Tests (back-end)
uv run python -m unittest discover back-end/tests
```

## Environment

Requires a `.env` file at project root:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

Neo4j container must be running (`make install`) before seeding the graph. The container uses the APOC plugin and is configured with up to 6 GB heap.

## Conventions

### Back-End (Python)

- **Python 3.14+**, managed with `uv`; never use pip or npm directly
- **Strict Pyright** — all code must pass `pyrightconfig.json` rules; add type hints to every function
- Helper functions are prefixed with `_`; constants use `UPPER_SNAKE_CASE` at module top
- Use `from __future__ import annotations` for forward references
- Progress output uses `print(..., flush=True)`; no logging module is used
- **N-tier structure**: `endpoints/ → services/ → repositories/ → core/database.py`
- DuckDB connection singleton in `core/database.py`; inject via `DuckDBDep` (Annotated type in `dependencies.py`)
- Neo4j is seeded in batches of 5,000 records per transaction; maintain this pattern for bulk writes
- Use the `_int()` / `_float()` helpers when reading IMDB data that may contain `\N` sentinel values
- **Service concurrency**: Use `ThreadPoolExecutor(max_workers=4)` for independent DuckDB queries within a single service call
- **Repository SQL templates**: SQL strings are module-level `_*_TEMPLATE` constants with `{source_table}` placeholders; `_resolve_source_relation()` maps boolean toggles to the correct DuckDB view or `None` (base tables)
- **Startup actions**: Register startup work in the `STARTUP_ACTIONS` tuple in `core/startup.py` as `(name, callable)` pairs
- **Pydantic schemas** live in `schemas/`; `models/` is intentionally empty
- **Tests**: `unittest`-based in `back-end/tests/`; use custom fake classes (e.g., `_FakeDuckDBConnection`) to mock DuckDB — never use real DB connections in unit tests

### Front-End (TypeScript)

- **Package manager**: Bun — never use npm; install packages with `bun add`, run scripts with `bun run`
- **Stack**: React 19 · React Router 7 · TypeScript strict · Vite 8 · Tailwind CSS 4 · shadcn/ui
- **Data fetching**: TanStack React Query 5 — `useQuery` with stable array keys; `keepPreviousData` for smooth refetches
- **State management**: `use-immer` — mutate draft in callbacks: `setFilters(draft => { draft.field = value })`
- **Filter state**: owned by `Analytics.tsx`, passed as props; `FilterPanel` is a controlled component
- Path alias `@` → `src/`
- Vite dev server on port 3000 proxies `/api/*` → `http://localhost:8000/*` (strips `/api` prefix)
- Add shadcn components: `bunx --bun shadcn@latest add <component>`
- Icons: `@hugeicons/react` (primary), `lucide-react` (secondary)

## Specs

All feature specifications live in `specs/`:

- [specs/back-end/filter_options.md](../specs/back-end/filter_options.md) — filter-options endpoint contract, SQL templates, source relation logic
- [specs/back-end/startup_check.md](../specs/back-end/startup_check.md) — startup action requirements
- [specs/front-end/filter_params.md](../specs/front-end/filter_params.md) — filter state flow, hook contract, refetch triggers
- [specs/patterns/front-end/custom_http_hook.md](../specs/patterns/front-end/custom_http_hook.md) — custom HTTP hook pattern

## Common Pitfalls

- `make seed` is slow (~30 min, ~1.5 GB download); use `make seed-sample` during development
- DuckDB holds an exclusive lock during Parquet conversion — don't query `imdb.duckdb` concurrently
- Parquet staleness check is 30 days; delete files manually to force a re-download
- If Pyright reports missing type stubs for a third-party library, add `# type: ignore` at the import
- Neo4j is seeded in batches of 5,000 records per transaction; maintain this pattern for bulk writes
- Use the `_int()` / `_float()` helpers when reading IMDB data that may contain `\N` sentinel values
