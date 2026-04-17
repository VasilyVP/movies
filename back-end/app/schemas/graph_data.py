from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.items_found import ItemsFoundParams


class GraphDataParams(ItemsFoundParams):
    pass


class GraphNode(BaseModel):
    id: str
    type: Literal["Title", "Person"]
    label: str
    titleType: str | None = None
    genres: list[str] | None = None
    startYear: int | None = None
    averageRating: float | None = None
    numVotes: int | None = None
    primaryProfession: list[str] | None = None
    birthYear: int | None = None
    deathYear: int | None = None
    isAnchor: bool
    score: float


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    category: str | None = None
    job: str | None = None
    characters: list[str] | None = None
    score: float


class GraphDataMeta(BaseModel):
    maxNodes: int
    maxEdges: int
    returnedNodes: int
    returnedEdges: int
    truncated: bool


def _default_nodes() -> list[GraphNode]:
    return []


def _default_edges() -> list[GraphEdge]:
    return []


class GraphDataResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=_default_nodes)
    edges: list[GraphEdge] = Field(default_factory=_default_edges)
    meta: GraphDataMeta
