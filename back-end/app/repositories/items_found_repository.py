from __future__ import annotations

from typing import Literal

import duckdb

SourceRelation = Literal[
    "all_titles_ratings",
    "top_rated_titles",
    "most_popular_titles",
    "top_rated_popular_titles",
]


def resolve_source_relation(top_rated: bool, most_popular: bool) -> SourceRelation:
    if top_rated and most_popular:
        return "top_rated_popular_titles"
    if top_rated:
        return "top_rated_titles"
    if most_popular:
        return "most_popular_titles"
    return "all_titles_ratings"


_COUNT_TITLES_TEMPLATE = """
SELECT COUNT(DISTINCT tb.tconst) AS total
FROM {source_table} tb
{name_join}
{where_clause}
"""

_COUNT_PERSONS_TEMPLATE = """
SELECT COUNT(DISTINCT nu.nconst) AS total
FROM name_unique nu
JOIN title_principals tp ON nu.nconst = tp.nconst
JOIN {source_table} tb ON tp.tconst = tb.tconst
{where_clause}
"""


def _build_title_clauses(
    title_id: str | None,
    name_id: str | None,
    title_type: str | None,
    genre: str | None,
    rating_from: float | None,
    rating_to: float | None,
    year_from: int | None,
    year_to: int | None,
) -> tuple[list[str], list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if title_id is not None:
        clauses.append("tb.tconst = ?")
        params.append(title_id)
    if name_id is not None:
        clauses.append("tp.nconst = ?")
        params.append(name_id)
    if title_type is not None:
        clauses.append("lower(tb.titleType) = lower(?)")
        params.append(title_type)
    if genre is not None:
        clauses.append(
            "list_contains(string_split(lower(COALESCE(tb.genres, '')), ','), lower(?))"
        )
        params.append(genre)
    if rating_from is not None:
        clauses.append("tb.averageRating >= ?")
        params.append(rating_from)
    if rating_to is not None:
        clauses.append("tb.averageRating <= ?")
        params.append(rating_to)
    if year_from is not None:
        clauses.append("CAST(tb.startYear AS INTEGER) >= ?")
        params.append(year_from)
    if year_to is not None:
        clauses.append("CAST(tb.startYear AS INTEGER) <= ?")
        params.append(year_to)

    return clauses, params


def _build_person_clauses(
    title_id: str | None,
    name_id: str | None,
    title_type: str | None,
    genre: str | None,
    rating_from: float | None,
    rating_to: float | None,
    year_from: int | None,
    year_to: int | None,
) -> tuple[list[str], list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if name_id is not None:
        clauses.append("nu.nconst = ?")
        params.append(name_id)
    if title_id is not None:
        clauses.append("tb.tconst = ?")
        params.append(title_id)
    if title_type is not None:
        clauses.append("lower(tb.titleType) = lower(?)")
        params.append(title_type)
    if genre is not None:
        clauses.append(
            "list_contains(string_split(lower(COALESCE(tb.genres, '')), ','), lower(?))"
        )
        params.append(genre)
    if rating_from is not None:
        clauses.append("tb.averageRating >= ?")
        params.append(rating_from)
    if rating_to is not None:
        clauses.append("tb.averageRating <= ?")
        params.append(rating_to)
    if year_from is not None:
        clauses.append("CAST(tb.startYear AS INTEGER) >= ?")
        params.append(year_from)
    if year_to is not None:
        clauses.append("CAST(tb.startYear AS INTEGER) <= ?")
        params.append(year_to)

    return clauses, params


def count_titles(
    duckdb_conn: duckdb.DuckDBPyConnection,
    *,
    top_rated: bool = False,
    most_popular: bool = False,
    title_id: str | None = None,
    name_id: str | None = None,
    title_type: str | None = None,
    genre: str | None = None,
    rating_from: float | None = None,
    rating_to: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> int:
    source_relation = resolve_source_relation(top_rated, most_popular)
    clauses, params = _build_title_clauses(
        title_id, name_id, title_type, genre, rating_from, rating_to, year_from, year_to
    )
    name_join = (
        "JOIN title_principals tp ON tb.tconst = tp.tconst"
        if name_id is not None
        else ""
    )
    where_clause = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = _COUNT_TITLES_TEMPLATE.format(
        source_table=source_relation,
        name_join=name_join,
        where_clause=where_clause,
    )
    row = duckdb_conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def count_persons(
    duckdb_conn: duckdb.DuckDBPyConnection,
    *,
    top_rated: bool = False,
    most_popular: bool = False,
    title_id: str | None = None,
    name_id: str | None = None,
    title_type: str | None = None,
    genre: str | None = None,
    rating_from: float | None = None,
    rating_to: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> int:
    source_relation = resolve_source_relation(top_rated, most_popular)
    clauses, params = _build_person_clauses(
        title_id, name_id, title_type, genre, rating_from, rating_to, year_from, year_to
    )
    where_clause = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = _COUNT_PERSONS_TEMPLATE.format(
        source_table=source_relation,
        where_clause=where_clause,
    )
    row = duckdb_conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0
