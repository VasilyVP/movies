from __future__ import annotations

import duckdb

from app.repositories import title_repository
from app.schemas.title import Title


def get_titles(
    duckdb: duckdb.DuckDBPyConnection,
    limit: int,
    offset: int,
) -> list[Title]:
    return title_repository.get_titles(duckdb, limit, offset)
