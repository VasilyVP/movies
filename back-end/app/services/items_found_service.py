from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict

import duckdb

from app.repositories import items_found_repository
from app.schemas.items_found import ItemsFoundParams, ItemsFoundResponse


class _CountKwargs(TypedDict, total=False):
    top_rated: bool
    most_popular: bool
    title_id: str | None
    name_id: str | None
    title_type: str | None
    genre: str | None
    rating_from: float | None
    rating_to: float | None
    year_from: int | None
    year_to: int | None


def _cursor_or_self(
    duckdb_conn: duckdb.DuckDBPyConnection,
) -> duckdb.DuckDBPyConnection:
    if hasattr(duckdb_conn, "cursor"):
        return duckdb_conn.cursor()
    return duckdb_conn


def get_items_found(
    duckdb_conn: duckdb.DuckDBPyConnection,
    params: ItemsFoundParams,
) -> ItemsFoundResponse:
    kwargs: _CountKwargs = {
        "top_rated": params.top_rated,
        "most_popular": params.most_popular,
        "title_id": params.title_id,
        "name_id": params.name_id,
        "title_type": params.title_type,
        "genre": params.genre,
        "rating_from": params.rating_range_from,
        "rating_to": params.rating_range_to,
        "year_from": params.release_year_from,
        "year_to": params.release_year_to,
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        titles_future = executor.submit(
            items_found_repository.count_titles,
            _cursor_or_self(duckdb_conn),
            **kwargs,
        )
        persons_future = executor.submit(
            items_found_repository.count_persons,
            _cursor_or_self(duckdb_conn),
            **kwargs,
        )
        total_titles = titles_future.result()
        total_persons = persons_future.result()

    return ItemsFoundResponse(
        totalTitles=total_titles,
        totalPersons=total_persons,
    )
