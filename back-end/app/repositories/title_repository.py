from __future__ import annotations

import duckdb

from app.schemas.title import Title

_QUERY = """
SELECT
    tb.tconst,
    tb.primaryTitle,
    tb.titleType,
    tb.startYear,
    tb.genres,
    tr.averageRating,
    tr.numVotes
FROM title_basics tb
LEFT JOIN title_ratings tr USING (tconst)
ORDER BY tb.tconst
LIMIT ? OFFSET ?
"""


def get_titles(
    duckdb: duckdb.DuckDBPyConnection,
    limit: int,
    offset: int,
) -> list[Title]:
    rows = duckdb.execute(_QUERY, [limit, offset]).fetchall()
    return [
        Title(
            tconst=row[0],
            primaryTitle=row[1],
            titleType=row[2],
            startYear=row[3],
            genres=row[4],
            averageRating=row[5],
            numVotes=row[6],
        )
        for row in rows
    ]
