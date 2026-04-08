# Spec: neo4j_seed.py

## Purpose

Seeds a local Neo4j instance from the DuckDB database (`back-end/data/imdb.duckdb`). Reads IMDB data via DuckDB and writes it to Neo4j as a property graph with `Person` and `Title` nodes connected by relationship edges.

---

## Usage

```bash
uv run python scripts/neo4j_seed.py [--limit N]
```

- `--limit N` — optional; seeds only the first N titles and their related persons/relationships (useful for development)
- Requires a `.env` file at the project root with `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- Neo4j container must be running before execution

---

## Configuration

| Constant        | Value                              | Description                              |
|-----------------|------------------------------------|------------------------------------------|
| `DUCKDB_PATH`   | `back-end/data/imdb.duckdb`        | Source database                          |
| `BATCH_SIZE`    | `5000`                             | Records per Neo4j transaction batch      |

---

## Execution Order

1. Load `.env` and connect to Neo4j (verify connectivity)
2. Open DuckDB in read-only mode
3. **Wipe** all existing nodes and relationships (DETACH DELETE, 10,000 rows per transaction)
4. **Create schema** — constraints and indexes
5. **Seed Person nodes**
6. **Seed Title nodes**
7. **Seed relationships**
8. Close DuckDB and Neo4j connections

---

## Graph Schema

### Nodes

#### `Person`
| Property           | Type        | Source column (name_unique)  |
|--------------------|-------------|------------------------------|
| `nconst`           | string (PK) | `nconst`                     |
| `primaryName`      | string      | `primaryName`                |
| `birthYear`        | int or null | `birthYear`                  |
| `deathYear`        | int or null | `deathYear`                  |
| `primaryProfession`| string      | `primaryProfession`          |
| `knownForTitles`   | string      | `knownForTitles`             |

When `--limit N` is given, only persons linked to the first N titles via `title_principals` are seeded.

#### `Title`
| Property         | Type         | Source columns (title_basics + title_ratings) |
|------------------|--------------|-----------------------------------------------|
| `tconst`         | string (PK)  | `title_basics.tconst`                         |
| `titleType`      | string       | `titleType`                                   |
| `primaryTitle`   | string       | `primaryTitle`                                |
| `originalTitle`  | string       | `originalTitle`                               |
| `isAdult`        | bool or null | `isAdult`                                     |
| `startYear`      | int or null  | `startYear`                                   |
| `endYear`        | int or null  | `endYear`                                     |
| `runtimeMinutes` | int or null  | `runtimeMinutes`                              |
| `genres`         | string       | `genres`                                      |
| `averageRating`  | float or null| `title_ratings.averageRating`                 |
| `numVotes`       | int or null  | `title_ratings.numVotes`                      |

Ratings are left-joined; titles without ratings have `null` for `averageRating` and `numVotes`.

### Relationships

Source table: `title_principals` (`tconst`, `nconst`, `category`, `job`, `characters`).

Direction: `(Person)-[REL_TYPE]->(Title)`

#### Relationship type mapping

| `category` value     | Relationship type |
|----------------------|-------------------|
| `actor`              | `ACTED_IN`        |
| `actress`            | `ACTED_IN`        |
| `director`           | `DIRECTED`        |
| `writer`             | `WROTE`           |
| `producer`           | `PRODUCED`        |
| `composer`           | `COMPOSED`        |
| `editor`             | `EDITED`          |
| `cinematographer`    | `SHOT`            |
| `production_designer`| `DESIGNED`        |
| `casting_director`   | `CAST`            |
| `self`               | `APPEARED_IN`     |
| `archive_footage`    | `APPEARED_IN`     |
| `archive_sound`      | `APPEARED_IN`     |
| *(any other)*        | `CATEGORY.upper().replace(" ", "_")` |

#### Relationship properties

| Property     | Type        | Notes                         |
|--------------|-------------|-------------------------------|
| `category`   | string      | Raw category from source      |
| `job`        | string/null | Specific job title            |
| `characters` | string/null | Character name(s) played      |

Relationships are grouped by type before writing; each type is written in separate batches.

---

## Constraints and Indexes

| Type                | Target                                |
|---------------------|---------------------------------------|
| Unique constraint   | `Person.nconst`                       |
| Unique constraint   | `Title.tconst`                        |
| Text index          | `Person.primaryName`                  |
| Text index          | `Title.primaryTitle`                  |
| Index               | `Title.startYear`                     |
| Index               | `Title.genres`                        |
| Index               | `Title.averageRating`                 |
| Index               | `Title.titleType`                     |
| Rel property index  | `ACTED_IN.category`                   |
| Rel property index  | `DIRECTED.category`                   |
| Rel property index  | `WROTE.category`                      |
| Rel property index  | `PRODUCED.category`                   |
| Rel property index  | `COMPOSED.category`                   |
| Rel property index  | `EDITED.category`                     |
| Rel property index  | `SHOT.category`                       |
| Rel property index  | `DESIGNED.category`                   |
| Rel property index  | `CAST.category`                       |
| Rel property index  | `APPEARED_IN.category`                |

All constraints and indexes use `IF NOT EXISTS` so the script is safe to re-run.

---

## Null Handling

IMDB uses `\N` as its null sentinel. The helpers `_null()`, `_int()`, and `_float()` convert this sentinel (and Python `None`) to `None` before writing to Neo4j.

---

## Progress Reporting

The script displays progress bars using `tqdm`. There are two levels of progress:

### Overall progress bar

A single outer bar tracks the major seeding phases. It is created before any phase begins and advances by one step as each phase completes.

| Step | Label shown in bar |
|------|--------------------|
| Wipe existing data | `Wiping existing data` |
| Create schema | `Creating schema` |
| Seed Person nodes | `Seeding Persons` |
| Seed Title nodes | `Seeding Titles` |
| Seed relationships | `Seeding relationships` |

Total = 5 steps. The bar is displayed with `desc="Overall"` and `total=5`.

### Per-phase progress bars

Each data-writing phase shows a nested inner bar that tracks batches written for that phase. The inner bar is created at the start of the phase and closed when the phase ends.

| Phase | `desc` label | `total` | Unit |
|-------|--------------|---------|------|
| Wipe existing data | `Wiping` | total node/rel count ÷ 10 000 (ceiling) | `batches` |
| Seed Person nodes | `Persons` | person count ÷ `BATCH_SIZE` (ceiling) | `batches` |
| Seed Title nodes | `Titles` | title count ÷ `BATCH_SIZE` (ceiling) | `batches` |
| Seed relationships (per type) | relationship type name (e.g. `ACTED_IN`) | row count for that type ÷ `BATCH_SIZE` (ceiling) | `batches` |

- The create-schema step has no inner bar (it executes a fixed set of Cypher statements, not batched data writes).
- Relationship types each get their own inner bar; they are created and closed sequentially, one per type.
- All bars use `leave=False` for the inner bars so they disappear after the phase is done, keeping the terminal clean.
- The overall bar uses `leave=True` so the final state remains visible after the script exits.
- Total counts are fetched from DuckDB with a `COUNT(*)` query before the phase begins so `tqdm` can display an accurate total and ETA.

---

## Dependencies

- `duckdb` — read-only source queries
- `neo4j` (official driver) — graph writes
- `python-dotenv` — `.env` loading
- `tqdm` — progress bars
- `argparse`, `os`, `time`, `pathlib` — stdlib

---

## Error Conditions

| Condition                          | Behaviour                                                    |
|------------------------------------|--------------------------------------------------------------|
| `.env` missing or incomplete       | `KeyError` on missing environment variable                   |
| Neo4j unreachable                  | `driver.verify_connectivity()` raises before any data is written |
| DuckDB file missing                | `duckdb.connect()` raises `IOException`                      |
| Person/Title node missing for a relationship | Cypher `MATCH` silently skips the row (no relationship created) |
