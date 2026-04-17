from __future__ import annotations

import math
from dataclasses import dataclass

import duckdb
from neo4j import GraphDatabase

from app.core.config import get_settings
from app.repositories import graph_data_repository
from app.schemas.graph_data import (
    GraphDataMeta,
    GraphDataParams,
    GraphDataResponse,
    GraphEdge,
    GraphNode,
)

MAX_NODES = 1_000
MAX_EDGES = 3_000
QUERY_EDGE_LIMIT = 6_000
CANDIDATE_ID_LIMIT = 1_000

_CORE_CATEGORIES = ["actor", "actress", "director", "writer", "composer", "producer"]

_REL_PRIORITY: dict[str, int] = {
    "DIRECTED": 0,
    "PRODUCED": 1,
    "WROTE": 2,
    "COMPOSED": 3,
    "ACTED_IN": 4,
}


@dataclass(frozen=True)
class _EdgeCandidate:
    edge: GraphEdge
    score: float
    priority_rank: int


@dataclass(frozen=True)
class _NodeCandidate:
    node: GraphNode
    score: float


def _split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    chunks = [item.strip() for item in value.split(",") if item.strip()]
    return chunks or None


def _edge_score(
    row: graph_data_repository.GraphRelationshipRow,
) -> tuple[float, int]:
    relation = row.rel_type.upper()
    priority_rank = _REL_PRIORITY.get(relation, 99)
    priority_weight = float(max(0, 10 - priority_rank))

    rating_component = (
        0.0 if row.title_rating is None else max(0.0, row.title_rating) / 10.0
    )
    if row.title_votes is None or row.title_votes <= 0:
        votes_component = 0.0
    else:
        votes_component = min(math.log10(float(row.title_votes)) / 7.0, 1.0)

    score = priority_weight + rating_component + votes_component
    return score, priority_rank


def _edge_id(
    row: graph_data_repository.GraphRelationshipRow,
) -> str:
    return f"{row.person_id}->{row.title_id}:{row.rel_type}"


def _characters_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith("[") and stripped.endswith("]"):
        content = stripped[1:-1].strip()
        if not content:
            return None
        return [
            part.strip().strip('"').strip("'")
            for part in content.split(",")
            if part.strip()
        ]
    return [stripped]


def _build_candidates(
    rows: list[graph_data_repository.GraphRelationshipRow],
    params: GraphDataParams,
) -> tuple[list[_EdgeCandidate], dict[str, _NodeCandidate]]:
    edge_candidates: list[_EdgeCandidate] = []
    node_scores: dict[str, float] = {}
    node_map: dict[str, GraphNode] = {}

    for row in rows:
        score, priority_rank = _edge_score(row)
        edge = GraphEdge(
            id=_edge_id(row),
            source=row.person_id,
            target=row.title_id,
            type=row.rel_type,
            category=row.rel_category,
            job=row.rel_job,
            characters=_characters_list(row.rel_characters),
            score=round(score, 6),
        )
        edge_candidates.append(
            _EdgeCandidate(edge=edge, score=score, priority_rank=priority_rank)
        )

        person_anchor = params.name_id is not None and row.person_id == params.name_id
        title_anchor = params.title_id is not None and row.title_id == params.title_id

        person_node = GraphNode(
            id=row.person_id,
            type="Person",
            label=row.person_name,
            primaryProfession=_split_csv(row.person_profession),
            birthYear=row.person_birth_year,
            deathYear=row.person_death_year,
            isAnchor=person_anchor,
            score=0.0,
        )
        title_node = GraphNode(
            id=row.title_id,
            type="Title",
            label=row.title_name,
            titleType=row.title_type,
            genres=_split_csv(row.title_genres),
            startYear=row.title_start_year,
            averageRating=row.title_rating,
            numVotes=row.title_votes,
            isAnchor=title_anchor,
            score=0.0,
        )

        node_map[row.person_id] = person_node
        node_map[row.title_id] = title_node
        node_scores[row.person_id] = max(node_scores.get(row.person_id, 0.0), score)
        node_scores[row.title_id] = max(node_scores.get(row.title_id, 0.0), score)

    node_candidates: dict[str, _NodeCandidate] = {}
    for node_id, node in node_map.items():
        node_score = round(node_scores.get(node_id, 0.0), 6)
        node_copy = node.model_copy(update={"score": node_score})
        node_candidates[node_id] = _NodeCandidate(
            node=node_copy, score=float(node_score)
        )

    return edge_candidates, node_candidates


def _empty_response(truncated: bool) -> GraphDataResponse:
    return GraphDataResponse(
        nodes=[],
        edges=[],
        meta=GraphDataMeta(
            maxNodes=MAX_NODES,
            maxEdges=MAX_EDGES,
            returnedNodes=0,
            returnedEdges=0,
            truncated=truncated,
        ),
    )


def get_graph_data(
    duckdb_conn: duckdb.DuckDBPyConnection,
    params: GraphDataParams,
) -> GraphDataResponse:
    candidates = graph_data_repository.fetch_candidate_ids(
        duckdb_conn,
        top_rated=params.top_rated,
        most_popular=params.most_popular,
        title_id=params.title_id,
        name_id=params.name_id,
        title_type=params.title_type,
        genre=params.genre,
        rating_from=params.rating_range_from,
        rating_to=params.rating_range_to,
        year_from=params.release_year_from,
        year_to=params.release_year_to,
        candidate_limit=CANDIDATE_ID_LIMIT,
    )

    preselection_truncated = (
        candidates.title_ids_truncated or candidates.person_ids_truncated
    )
    if not candidates.title_ids:
        return _empty_response(preselection_truncated)

    if (
        params.name_id is None
        and params.title_id is None
        and not candidates.person_ids
    ):
        return _empty_response(preselection_truncated)

    settings = get_settings()

    driver = GraphDatabase.driver(  # type: ignore
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        rows = graph_data_repository.fetch_graph_rows(
            driver,
            candidate_title_ids=candidates.title_ids,
            candidate_person_ids=candidates.person_ids,
            anchor_name_id=params.name_id,
            anchor_title_id=params.title_id,
            core_categories=_CORE_CATEGORIES,
            edge_limit=QUERY_EDGE_LIMIT,
        )
    finally:
        driver.close()

    edge_candidates, node_candidates = _build_candidates(rows, params)

    ordered_edges = sorted(
        edge_candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.priority_rank,
            candidate.edge.id,
        ),
    )
    selected_edges = ordered_edges[:MAX_EDGES]

    ordered_nodes = sorted(
        node_candidates.values(),
        key=lambda candidate: (
            -candidate.score,
            candidate.node.id,
        ),
    )
    selected_node_ids = [candidate.node.id for candidate in ordered_nodes[:MAX_NODES]]
    selected_node_set = set(selected_node_ids)

    selected_edges_final = [
        candidate.edge
        for candidate in selected_edges
        if candidate.edge.source in selected_node_set
        and candidate.edge.target in selected_node_set
    ]

    selected_nodes = [node_candidates[node_id].node for node_id in selected_node_ids]
    selected_nodes.sort(key=lambda node: (-node.score, node.id))
    selected_edges_final.sort(key=lambda edge: (-edge.score, edge.id))

    truncated = (
        preselection_truncated
        or len(edge_candidates) > MAX_EDGES
        or len(node_candidates) > MAX_NODES
    )
    if len(selected_edges_final) < len(selected_edges):
        truncated = True

    return GraphDataResponse(
        nodes=selected_nodes,
        edges=selected_edges_final,
        meta=GraphDataMeta(
            maxNodes=MAX_NODES,
            maxEdges=MAX_EDGES,
            returnedNodes=len(selected_nodes),
            returnedEdges=len(selected_edges_final),
            truncated=truncated,
        ),
    )
