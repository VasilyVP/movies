from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Any, LiteralString

import duckdb
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase  # type: ignore
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DUCKDB_PATH = "back-end/data/imdb.duckdb"
BATCH_SIZE = 5_000
WIPE_BATCH_SIZE = 10_000

_BAR_FORMAT = "{desc}: {percentage:3.0f}%|{bar}| [{elapsed}<{remaining}]"

_CATEGORY_MAP: dict[str, str] = {
    "actor": "ACTED_IN",
    "actress": "ACTED_IN",
    "director": "DIRECTED",
    "writer": "WROTE",
    "producer": "PRODUCED",
    "composer": "COMPOSED",
    "editor": "EDITED",
    "cinematographer": "SHOT",
    "production_designer": "DESIGNED",
    "casting_director": "CAST",
    "self": "APPEARED_IN",
    "archive_footage": "APPEARED_IN",
    "archive_sound": "APPEARED_IN",
}

_SCHEMA_STATEMENTS: list[LiteralString] = [
    "CREATE CONSTRAINT person_nconst IF NOT EXISTS FOR (p:Person) REQUIRE p.nconst IS UNIQUE",
    "CREATE CONSTRAINT title_tconst IF NOT EXISTS FOR (t:Title) REQUIRE t.tconst IS UNIQUE",
    "CREATE TEXT INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.primaryName)",
    "CREATE TEXT INDEX title_name IF NOT EXISTS FOR (t:Title) ON (t.primaryTitle)",
    "CREATE INDEX title_year IF NOT EXISTS FOR (t:Title) ON (t.startYear)",
    "CREATE INDEX title_genres IF NOT EXISTS FOR (t:Title) ON (t.genres)",
    "CREATE INDEX title_rating IF NOT EXISTS FOR (t:Title) ON (t.averageRating)",
    "CREATE INDEX title_type IF NOT EXISTS FOR (t:Title) ON (t.titleType)",
    "CREATE INDEX acted_in_cat IF NOT EXISTS FOR ()-[r:ACTED_IN]->() ON (r.category)",
    "CREATE INDEX directed_cat IF NOT EXISTS FOR ()-[r:DIRECTED]->() ON (r.category)",
    "CREATE INDEX wrote_cat IF NOT EXISTS FOR ()-[r:WROTE]->() ON (r.category)",
    "CREATE INDEX produced_cat IF NOT EXISTS FOR ()-[r:PRODUCED]->() ON (r.category)",
    "CREATE INDEX composed_cat IF NOT EXISTS FOR ()-[r:COMPOSED]->() ON (r.category)",
    "CREATE INDEX edited_cat IF NOT EXISTS FOR ()-[r:EDITED]->() ON (r.category)",
    "CREATE INDEX shot_cat IF NOT EXISTS FOR ()-[r:SHOT]->() ON (r.category)",
    "CREATE INDEX designed_cat IF NOT EXISTS FOR ()-[r:DESIGNED]->() ON (r.category)",
    "CREATE INDEX cast_cat IF NOT EXISTS FOR ()-[r:CAST]->() ON (r.category)",
    "CREATE INDEX appeared_in_cat IF NOT EXISTS FOR ()-[r:APPEARED_IN]->() ON (r.category)",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _null(value: object) -> object | None:
    if value is None or value == r"\N":
        return None
    return value


def _int(value: object) -> int | None:
    v = _null(value)
    if v is None:
        return None
    return int(v)  # type: ignore[arg-type]


def _float(value: object) -> float | None:
    v = _null(value)
    if v is None:
        return None
    return float(v)  # type: ignore[arg-type]


def _bool(value: object) -> bool | None:
    v = _null(value)
    if v is None:
        return None
    return bool(int(v))  # type: ignore[arg-type]


def _category_to_rel(category: str) -> str:
    return _CATEGORY_MAP.get(category, category.upper().replace(" ", "_"))


def _count(
    db_conn: duckdb.DuckDBPyConnection,
    query: str,
    params: list[Any] | None = None,
) -> int:
    result = db_conn.execute(query, params) if params else db_conn.execute(query)
    row = result.fetchone()
    return int(row[0]) if row is not None else 0


def _limited_titles_subquery(limit: int) -> str:
    # Keep --limit deterministic across all phases so person/title/relationship subsets match.
    return f"SELECT tconst FROM title_basics ORDER BY tconst LIMIT {limit}"


# ---------------------------------------------------------------------------
# Seeding phases
# ---------------------------------------------------------------------------


def _wipe(driver: Driver, inner_bar: tqdm[Any]) -> None:
    with driver.session() as session:  # type: ignore[union-attr]
        record = session.run("MATCH (n) RETURN count(n) AS c").single()
        node_count = int(record["c"]) if record is not None else 0  # type: ignore[index]

    batches = max(1, math.ceil(node_count / WIPE_BATCH_SIZE))
    inner_bar.reset(total=batches)
    inner_bar.set_description("Wiping")

    if node_count == 0:
        inner_bar.update(1)
        return

    while True:
        with driver.session() as session:  # type: ignore[union-attr]
            result = session.run(
                "MATCH (n) WITH n LIMIT $limit DETACH DELETE n",
                limit=WIPE_BATCH_SIZE,
            )
            summary = result.consume()
        inner_bar.update(1)
        if summary.counters.nodes_deleted == 0:
            break


def _create_schema(driver: Driver, inner_bar: tqdm[Any]) -> None:
    inner_bar.reset(total=1)
    inner_bar.set_description("Creating schema")
    with driver.session() as session:  # type: ignore[union-attr]
        for stmt in _SCHEMA_STATEMENTS:
            session.run(stmt)
    inner_bar.update(1)


def _seed_persons(
    driver: Driver,
    db_conn: duckdb.DuckDBPyConnection,
    limit: int | None,
    inner_bar: tqdm[Any],
) -> None:
    if limit is not None:
        subq = f"SELECT DISTINCT nconst FROM title_principals WHERE tconst IN ({_limited_titles_subquery(limit)})"
        count_q = f"SELECT COUNT(*) FROM name_unique WHERE nconst IN ({subq})"
        data_q = f"SELECT nconst, primaryName, birthYear, deathYear, primaryProfession, knownForTitles FROM name_unique WHERE nconst IN ({subq})"
    else:
        count_q = "SELECT COUNT(*) FROM name_unique"
        data_q = "SELECT nconst, primaryName, birthYear, deathYear, primaryProfession, knownForTitles FROM name_unique"

    total = _count(db_conn, count_q)
    inner_bar.reset(total=max(1, math.ceil(total / BATCH_SIZE)))
    inner_bar.set_description("Persons")

    cypher = """
        UNWIND $batch AS row
        MERGE (p:Person {nconst: row.nconst})
        SET p.primaryName       = row.primaryName,
            p.birthYear         = row.birthYear,
            p.deathYear         = row.deathYear,
            p.primaryProfession = row.primaryProfession,
            p.knownForTitles    = row.knownForTitles
    """
    cursor = db_conn.execute(data_q)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        batch: list[dict[str, Any]] = [
            {
                "nconst": row[0],
                "primaryName": _null(row[1]),
                "birthYear": _int(row[2]),
                "deathYear": _int(row[3]),
                "primaryProfession": _null(row[4]),
                "knownForTitles": _null(row[5]),
            }
            for row in rows
        ]
        with driver.session() as session:  # type: ignore[union-attr]
            session.run(cypher, batch=batch)
        inner_bar.update(1)


def _seed_titles(
    driver: Driver,
    db_conn: duckdb.DuckDBPyConnection,
    limit: int | None,
    inner_bar: tqdm[Any],
) -> None:
    if limit is not None:
        limited_titles = _limited_titles_subquery(limit)
        count_q = f"SELECT COUNT(*) FROM ({limited_titles})"
        data_q = f"""
            WITH limited_titles AS ({limited_titles})
            SELECT tb.tconst, tb.titleType, tb.primaryTitle, tb.originalTitle,
                   tb.isAdult, tb.startYear, tb.endYear, tb.runtimeMinutes, tb.genres,
                   tr.averageRating, tr.numVotes
            FROM limited_titles lt
            JOIN title_basics tb ON tb.tconst = lt.tconst
            LEFT JOIN title_ratings tr ON tb.tconst = tr.tconst
            ORDER BY tb.tconst
        """
    else:
        count_q = "SELECT COUNT(*) FROM title_basics"
        data_q = """
            SELECT tb.tconst, tb.titleType, tb.primaryTitle, tb.originalTitle,
                   tb.isAdult, tb.startYear, tb.endYear, tb.runtimeMinutes, tb.genres,
                   tr.averageRating, tr.numVotes
            FROM title_basics tb
            LEFT JOIN title_ratings tr ON tb.tconst = tr.tconst
        """

    total = _count(db_conn, count_q)
    inner_bar.reset(total=max(1, math.ceil(total / BATCH_SIZE)))
    inner_bar.set_description("Titles")

    cypher = """
        UNWIND $batch AS row
        MERGE (t:Title {tconst: row.tconst})
        SET t.titleType      = row.titleType,
            t.primaryTitle   = row.primaryTitle,
            t.originalTitle  = row.originalTitle,
            t.isAdult        = row.isAdult,
            t.startYear      = row.startYear,
            t.endYear        = row.endYear,
            t.runtimeMinutes = row.runtimeMinutes,
            t.genres         = row.genres,
            t.averageRating  = row.averageRating,
            t.numVotes       = row.numVotes
    """
    cursor = db_conn.execute(data_q)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        batch: list[dict[str, Any]] = [
            {
                "tconst": row[0],
                "titleType": _null(row[1]),
                "primaryTitle": _null(row[2]),
                "originalTitle": _null(row[3]),
                "isAdult": _bool(row[4]),
                "startYear": _int(row[5]),
                "endYear": _int(row[6]),
                "runtimeMinutes": _int(row[7]),
                "genres": _null(row[8]),
                "averageRating": _float(row[9]),
                "numVotes": _int(row[10]),
            }
            for row in rows
        ]
        with driver.session() as session:  # type: ignore[union-attr]
            session.run(cypher, batch=batch)
        inner_bar.update(1)


def _seed_relationships(
    driver: Driver,
    db_conn: duckdb.DuckDBPyConnection,
    limit: int | None,
    inner_bar: tqdm[Any],
) -> None:
    limit_filter = (
        f"tconst IN ({_limited_titles_subquery(limit)})"
        if limit is not None
        else "TRUE"
    )

    all_cats: list[str] = [
        str(row[0])
        for row in db_conn.execute(
            f"SELECT DISTINCT category FROM title_principals WHERE {limit_filter} AND category IS NOT NULL"
        ).fetchall()
    ]

    rel_groups: dict[str, list[str]] = {}
    for cat in all_cats:
        rel_groups.setdefault(_category_to_rel(cat), []).append(cat)

    expected_total = 0
    created_total = 0
    skipped_total = 0
    missing_person_total = 0
    missing_title_total = 0
    missing_both_total = 0

    for rel_type, cats in rel_groups.items():
        placeholders = ", ".join("?" * len(cats))
        total = _count(
            db_conn,
            f"SELECT COUNT(*) FROM title_principals WHERE category IN ({placeholders}) AND {limit_filter}",
            cats,
        )
        if total == 0:
            continue

        expected_total += total

        inner_bar.reset(total=math.ceil(total / BATCH_SIZE))
        inner_bar.set_description(rel_type)

        cypher = f"""
            UNWIND $batch AS row
            MATCH (p:Person {{nconst: row.nconst}})
            MATCH (t:Title {{tconst: row.tconst}})
            CREATE (p)-[:{rel_type} {{category: row.category, job: row.job, characters: row.characters}}]->(t)
            RETURN count(*) AS created_count
        """

        diagnostics_cypher = """
            UNWIND $batch AS row
            OPTIONAL MATCH (p:Person {nconst: row.nconst})
            OPTIONAL MATCH (t:Title {tconst: row.tconst})
            RETURN
                sum(CASE WHEN p IS NULL THEN 1 ELSE 0 END) AS missing_person,
                sum(CASE WHEN t IS NULL THEN 1 ELSE 0 END) AS missing_title,
                sum(CASE WHEN p IS NULL AND t IS NULL THEN 1 ELSE 0 END) AS missing_both
        """

        cursor = db_conn.execute(
            f"SELECT tconst, nconst, category, job, characters FROM title_principals WHERE category IN ({placeholders}) AND {limit_filter}",
            cats,
        )
        while True:
            rows = cursor.fetchmany(BATCH_SIZE)
            if not rows:
                break
            batch: list[dict[str, Any]] = [
                {
                    "tconst": row[0],
                    "nconst": row[1],
                    "category": _null(row[2]),
                    "job": _null(row[3]),
                    "characters": _null(row[4]),
                }
                for row in rows
            ]
            with driver.session() as session:  # type: ignore[union-attr]
                created_record = session.run(cypher, batch=batch).single()  # type: ignore[arg-type]
                created_in_batch = int(created_record["created_count"]) if created_record is not None else 0  # type: ignore[index]
                attempted_in_batch = len(batch)
                skipped_in_batch = attempted_in_batch - created_in_batch

                created_total += created_in_batch
                skipped_total += skipped_in_batch

                if skipped_in_batch > 0:
                    diagnostics_record = session.run(diagnostics_cypher, batch=batch).single()  # type: ignore[arg-type]
                    missing_person = int(diagnostics_record["missing_person"]) if diagnostics_record is not None else 0  # type: ignore[index]
                    missing_title = int(diagnostics_record["missing_title"]) if diagnostics_record is not None else 0  # type: ignore[index]
                    missing_both = int(diagnostics_record["missing_both"]) if diagnostics_record is not None else 0  # type: ignore[index]
                    missing_person_total += missing_person
                    missing_title_total += missing_title
                    missing_both_total += missing_both

            inner_bar.update(1)
    if expected_total > 0 and created_total == 0:
        raise RuntimeError(
            "Relationship seeding failed: DuckDB returned rows but Neo4j created 0 relationships. "
            "Check Person/Title node matching and relationship diagnostics output."
        )

    if created_total != expected_total:
        print(
            "Relationship seeding mismatch: "
            f"expected={expected_total}, created={created_total}, skipped={skipped_total}, "
            f"missing_person={missing_person_total}, missing_title={missing_title_total}, "
            f"missing_both={missing_both_total}."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("Seeding Neo4j from DuckDB IMDB data...", flush=True)

    parser = argparse.ArgumentParser(description="Seed Neo4j from DuckDB IMDB data.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Seed only the first N titles"
    )
    args = parser.parse_args()
    limit: int | None = args.limit

    load_dotenv()
    neo4j_uri = os.environ["NEO4J_URI"]
    neo4j_user = os.environ["NEO4J_USER"]
    neo4j_password = os.environ["NEO4J_PASSWORD"]

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))  # type: ignore[misc]
    db_conn: duckdb.DuckDBPyConnection | None = None

    try:
        driver.verify_connectivity()  # type: ignore[misc]

        db_conn = duckdb.connect(str(Path(DUCKDB_PATH)), read_only=True)

        overall_bar: tqdm[Any] = tqdm(
            total=5,
            desc="Overall",
            bar_format=_BAR_FORMAT,
            position=0,
            leave=True,
        )
        inner_bar: tqdm[Any] = tqdm(
            total=1,
            desc="",
            bar_format=_BAR_FORMAT,
            position=1,
            leave=False,
        )

        try:
            _wipe(driver, inner_bar)
            overall_bar.update(1)

            _create_schema(driver, inner_bar)
            overall_bar.update(1)

            _seed_persons(driver, db_conn, limit, inner_bar)
            overall_bar.update(1)

            _seed_titles(driver, db_conn, limit, inner_bar)
            overall_bar.update(1)

            _seed_relationships(driver, db_conn, limit, inner_bar)
            overall_bar.update(1)
        finally:
            inner_bar.close()
            overall_bar.close()

        total_time = str(
            overall_bar.format_interval(overall_bar.format_dict["elapsed"])
        )
        print(f"Done in: {total_time}s", flush=True)

    finally:
        if db_conn is not None:
            db_conn.close()
        driver.close()


if __name__ == "__main__":
    main()
