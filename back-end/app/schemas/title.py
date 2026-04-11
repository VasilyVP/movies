from __future__ import annotations

from pydantic import BaseModel


class Title(BaseModel):
    tconst: str
    primaryTitle: str
    titleType: str | None
    startYear: int | None
    genres: str | None
    averageRating: float | None
    numVotes: int | None
