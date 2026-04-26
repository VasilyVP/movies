from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb
from neo4j import Driver

from app.repositories.items_found_repository import resolve_source_relation


@dataclass(frozen=True)
class GraphCandidateIds:
    title_ids: list[str]
    person_ids: list[str]
    title_ids_truncated: bool
    person_ids_truncated: bool


class GraphRelationshipRow:
    def __init__(
        self,
        person_id: str,
        person_name: str,
        person_profession: str | None,
        person_birth_year: int | None,
        person_death_year: int | None,
        title_id: str,
        title_name: str,
        title_type: str | None,
        title_genres: str | None,
        title_start_year: int | None,
        title_rating: float | None,
        title_votes: int | None,
        rel_type: str,
        rel_category: str | None,
        rel_job: str | None,
        rel_characters: str | None,
    ):
        self.person_id = person_id
        self.person_name = person_name
        self.person_profession = person_profession
        self.person_birth_year = person_birth_year
        self.person_death_year = person_death_year
        self.title_id = title_id
        self.title_name = title_name
        self.title_type = title_type
        self.title_genres = title_genres
        self.title_start_year = title_start_year
        self.title_rating = title_rating
        self.title_votes = title_votes
        self.rel_type = rel_type
        self.rel_category = rel_category
        self.rel_job = rel_job
        self.rel_characters = rel_characters


def _to_int(value: Any) -> int | None:
    if value is None or value == "\\N":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "\\N":
        return None
    try:
        return float(value)
    except Exception:
        return None


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


_TITLE_CANDIDATE_TEMPLATE = """
SELECT DISTINCT tb.tconst AS id
FROM {source_table} tb
{name_join}
{where_clause}
ORDER BY tb.tconst
LIMIT ?
"""

_PERSON_CANDIDATE_TEMPLATE = """
SELECT DISTINCT nu.nconst AS id
FROM name_unique nu
JOIN title_principals tp ON nu.nconst = tp.nconst
JOIN {source_table} tb ON tp.tconst = tb.tconst
{where_clause}
ORDER BY nu.nconst
LIMIT ?
"""


def _cap_ids(rows: list[tuple[object, ...]], limit: int) -> tuple[list[str], bool]:
    ids = [str(row[0]) for row in rows if row]
    truncated = len(ids) > limit
    return ids[:limit], truncated


def fetch_candidate_ids(
    duckdb_conn: duckdb.DuckDBPyConnection,
    *,
    top_rated: bool,
    most_popular: bool,
    title_id: str | None,
    name_id: str | None,
    title_type: str | None,
    genre: str | None,
    rating_from: float | None,
    rating_to: float | None,
    year_from: int | None,
    year_to: int | None,
    candidate_limit: int,
) -> GraphCandidateIds:
    source_relation = resolve_source_relation(top_rated, most_popular)

    title_clauses, title_params = _build_title_clauses(
        title_id,
        name_id,
        title_type,
        genre,
        rating_from,
        rating_to,
        year_from,
        year_to,
    )
    title_name_join = (
        "JOIN title_principals tp ON tb.tconst = tp.tconst" if name_id is not None else ""
    )
    title_where_clause = (
        "WHERE " + " AND ".join(title_clauses) if title_clauses else ""
    )
    title_sql = _TITLE_CANDIDATE_TEMPLATE.format(
        source_table=source_relation,
        name_join=title_name_join,
        where_clause=title_where_clause,
    )
    title_rows = duckdb_conn.execute(
        title_sql,
        [*title_params, candidate_limit + 1],
    ).fetchall()

    person_clauses, person_params = _build_person_clauses(
        title_id,
        name_id,
        title_type,
        genre,
        rating_from,
        rating_to,
        year_from,
        year_to,
    )
    person_where_clause = (
        "WHERE " + " AND ".join(person_clauses) if person_clauses else ""
    )
    person_sql = _PERSON_CANDIDATE_TEMPLATE.format(
        source_table=source_relation,
        where_clause=person_where_clause,
    )
    person_rows = duckdb_conn.execute(
        person_sql,
        [*person_params, candidate_limit + 1],
    ).fetchall()

    title_ids, title_ids_truncated = _cap_ids(title_rows, candidate_limit)
    person_ids, person_ids_truncated = _cap_ids(person_rows, candidate_limit)

    return GraphCandidateIds(
        title_ids=title_ids,
        person_ids=person_ids,
        title_ids_truncated=title_ids_truncated,
        person_ids_truncated=person_ids_truncated,
    )


GRAPH_DATA_CYPHER = """
WITH
    $anchor_name_id AS anchor_name_id,
    $anchor_title_id AS anchor_title_id,
    $candidate_title_ids AS candidate_title_ids,
    $candidate_person_ids AS candidate_person_ids,
    $core_categories AS core_categories
WITH
    anchor_name_id,
    anchor_title_id,
    candidate_title_ids,
    candidate_person_ids,
    core_categories,
    anchor_name_id IS NOT NULL AS has_name_anchor,
    anchor_title_id IS NOT NULL AS has_title_anchor
CALL (
    anchor_name_id,
    anchor_title_id,
    candidate_title_ids,
    candidate_person_ids,
    core_categories,
    has_name_anchor,
    has_title_anchor
) {
    WITH
        anchor_name_id,
        anchor_title_id,
        candidate_title_ids,
        candidate_person_ids,
        core_categories,
        has_name_anchor,
        has_title_anchor
    WITH
        anchor_name_id,
        anchor_title_id,
        candidate_title_ids,
        candidate_person_ids,
        core_categories,
        has_name_anchor,
        has_title_anchor
    WHERE has_name_anchor
    MATCH (:Person {nconst: anchor_name_id})-[ar]->(t:Title)
    WHERE ar.category IN core_categories
        AND t.tconst IN candidate_title_ids
    RETURN DISTINCT t.tconst AS expanded_title_id

    UNION

    WITH
        anchor_name_id,
        anchor_title_id,
        candidate_title_ids,
        candidate_person_ids,
        core_categories,
        has_name_anchor,
        has_title_anchor
    WITH
        anchor_name_id,
        anchor_title_id,
        candidate_title_ids,
        candidate_person_ids,
        core_categories,
        has_name_anchor,
        has_title_anchor
    WHERE (NOT has_name_anchor) AND has_title_anchor
    MATCH (seed:Person)-[sr]->(:Title {tconst: anchor_title_id})
    WHERE sr.category IN core_categories
    MATCH (seed)-[er]->(t:Title)
    WHERE er.category IN core_categories
        AND t.tconst IN candidate_title_ids
    RETURN DISTINCT t.tconst AS expanded_title_id

    UNION

    WITH
        anchor_name_id,
        anchor_title_id,
        candidate_title_ids,
        candidate_person_ids,
        core_categories,
        has_name_anchor,
        has_title_anchor
    WITH
        anchor_name_id,
        anchor_title_id,
        candidate_title_ids,
        candidate_person_ids,
        core_categories,
        has_name_anchor,
        has_title_anchor
    WHERE (NOT has_name_anchor) AND (NOT has_title_anchor)
    MATCH (p:Person)-[r]->(t:Title)
    WHERE r.category IN core_categories
        AND t.tconst IN candidate_title_ids
        AND p.nconst IN candidate_person_ids
    RETURN DISTINCT t.tconst AS expanded_title_id
}
WITH expanded_title_id, core_categories
MATCH (p:Person)-[r]->(t:Title {tconst: expanded_title_id})
WHERE r.category IN core_categories
RETURN
    p.nconst AS person_id,
    coalesce(p.primaryName, p.nconst) AS person_name,
    p.primaryProfession AS person_profession,
    p.birthYear AS person_birth_year,
    p.deathYear AS person_death_year,
    t.tconst AS title_id,
    coalesce(t.primaryTitle, t.tconst) AS title_name,
    t.titleType AS title_type,
    t.genres AS title_genres,
    t.startYear AS title_start_year,
    t.averageRating AS title_rating,
    t.numVotes AS title_votes,
    type(r) AS rel_type,
    r.category AS rel_category,
    r.job AS rel_job,
    r.characters AS rel_characters
LIMIT $edge_limit
"""


def fetch_graph_rows(
    driver: Driver,
    *,
    candidate_title_ids: list[str],
    candidate_person_ids: list[str],
    anchor_name_id: str | None,
    anchor_title_id: str | None,
    core_categories: list[str],
    edge_limit: int,
) -> list[GraphRelationshipRow]:
    query_params: dict[str, object] = {
        "candidate_title_ids": candidate_title_ids,
        "candidate_person_ids": candidate_person_ids,
        "anchor_name_id": anchor_name_id,
        "anchor_title_id": anchor_title_id,
        "core_categories": core_categories,
        "edge_limit": edge_limit,
    }

    with driver.session() as session:  # type: ignore
        result = session.run(GRAPH_DATA_CYPHER, query_params)
        rows = list(result)

    output: list[GraphRelationshipRow] = []
    for row in rows:
        values: dict[str, Any] = dict(row)
        output.append(
            GraphRelationshipRow(
                person_id=str(values["person_id"]),
                person_name=str(values["person_name"]),
                person_profession=(
                    None
                    if values.get("person_profession") is None
                    else str(values["person_profession"])
                ),
                person_birth_year=_to_int(values.get("person_birth_year")),
                person_death_year=_to_int(values.get("person_death_year")),
                title_id=str(values["title_id"]),
                title_name=str(values["title_name"]),
                title_type=(
                    None
                    if values.get("title_type") is None
                    else str(values["title_type"])
                ),
                title_genres=(
                    None
                    if values.get("title_genres") is None
                    else str(values["title_genres"])
                ),
                title_start_year=_to_int(values.get("title_start_year")),
                title_rating=_to_float(values.get("title_rating")),
                title_votes=_to_int(values.get("title_votes")),
                rel_type=str(values["rel_type"]),
                rel_category=(
                    None
                    if values.get("rel_category") is None
                    else str(values["rel_category"])
                ),
                rel_job=(
                    None if values.get("rel_job") is None else str(values["rel_job"])
                ),
                rel_characters=(
                    None
                    if values.get("rel_characters") is None
                    else str(values["rel_characters"])
                ),
            )
        )

    return output
