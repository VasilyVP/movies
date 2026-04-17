from __future__ import annotations

import unittest
from unittest.mock import patch

from app.repositories import items_found_repository
from app.schemas.items_found import ItemsFoundParams, ItemsFoundResponse
from app.services import items_found_service


class _FakeDuckDBConnection:
    def __init__(self, fetchone_result: tuple[object, ...] = (0,)) -> None:
        self._fetchone_result = fetchone_result
        self.last_sql = ""
        self.last_params: list[object] = []

    def cursor(self) -> "_FakeDuckDBConnection":
        return _FakeDuckDBConnection(self._fetchone_result)

    def execute(self, sql: str, params: list[object]) -> "_FakeDuckDBConnection":
        self.last_sql = " ".join(sql.split())
        self.last_params = list(params)
        return self

    def fetchone(self) -> tuple[object, ...]:
        return self._fetchone_result


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class ItemsFoundParamsTests(unittest.TestCase):
    def test_defaults_are_false_and_none(self) -> None:
        p = ItemsFoundParams()
        self.assertFalse(p.top_rated)
        self.assertFalse(p.most_popular)
        self.assertIsNone(p.title_id)
        self.assertIsNone(p.name_id)
        self.assertIsNone(p.title_type)
        self.assertIsNone(p.genre)
        self.assertIsNone(p.rating_range_from)
        self.assertIsNone(p.rating_range_to)
        self.assertIsNone(p.release_year_from)
        self.assertIsNone(p.release_year_to)

    def test_rejects_inverted_rating_range(self) -> None:
        with self.assertRaisesRegex(Exception, "ratingRangeFrom"):
            ItemsFoundParams(ratingRangeFrom=9.0, ratingRangeTo=7.0)

    def test_accepts_equal_rating_range(self) -> None:
        p = ItemsFoundParams(ratingRangeFrom=8.0, ratingRangeTo=8.0)
        self.assertEqual(p.rating_range_from, 8.0)

    def test_rejects_inverted_year_range(self) -> None:
        with self.assertRaisesRegex(Exception, "releaseYearFrom"):
            ItemsFoundParams(releaseYearFrom=2020, releaseYearTo=2010)

    def test_accepts_equal_year_range(self) -> None:
        p = ItemsFoundParams(releaseYearFrom=2000, releaseYearTo=2000)
        self.assertEqual(p.release_year_from, 2000)


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class ItemsFoundRepositoryTests(unittest.TestCase):
    def test_count_titles_no_filters_uses_default_source(self) -> None:
        conn = _FakeDuckDBConnection((42,))
        result = items_found_repository.count_titles(
            conn,  # type: ignore[arg-type]
        )
        self.assertEqual(result, 42)
        self.assertIn("all_titles_ratings", conn.last_sql)
        self.assertNotIn("WHERE", conn.last_sql)

    def test_count_titles_with_name_id_adds_join_and_clause(self) -> None:
        conn = _FakeDuckDBConnection((5,))
        items_found_repository.count_titles(
            conn,  # type: ignore[arg-type]
            name_id="nm0000209",
        )
        self.assertIn(
            "JOIN title_principals tp ON tb.tconst = tp.tconst", conn.last_sql
        )
        self.assertIn("tp.nconst = ?", conn.last_sql)
        self.assertIn("nm0000209", conn.last_params)

    def test_count_titles_rating_uses_tb_alias(self) -> None:
        conn = _FakeDuckDBConnection((10,))
        items_found_repository.count_titles(
            conn,  # type: ignore[arg-type]
            rating_from=7.0,
            rating_to=9.0,
        )
        self.assertIn("tb.averageRating >= ?", conn.last_sql)
        self.assertIn("tb.averageRating <= ?", conn.last_sql)
        self.assertNotIn("tr.averageRating", conn.last_sql)

    def test_count_titles_top_rated_source_relation(self) -> None:
        source = items_found_repository.resolve_source_relation(True, False)
        self.assertEqual(source, "top_rated_titles")

    def test_count_titles_both_flags_source_relation(self) -> None:
        source = items_found_repository.resolve_source_relation(True, True)
        self.assertEqual(source, "top_rated_popular_titles")

    def test_count_titles_most_popular_source_relation(self) -> None:
        source = items_found_repository.resolve_source_relation(False, True)
        self.assertEqual(source, "most_popular_titles")

    def test_count_titles_default_source_relation(self) -> None:
        source = items_found_repository.resolve_source_relation(False, False)
        self.assertEqual(source, "all_titles_ratings")

    def test_count_persons_no_filters_joins_three_tables(self) -> None:
        conn = _FakeDuckDBConnection((99,))
        result = items_found_repository.count_persons(
            conn,  # type: ignore[arg-type]
        )
        self.assertEqual(result, 99)
        self.assertIn("name_unique nu", conn.last_sql)
        self.assertIn(
            "JOIN title_principals tp ON nu.nconst = tp.nconst", conn.last_sql
        )
        self.assertIn(
            "JOIN all_titles_ratings tb ON tp.tconst = tb.tconst", conn.last_sql
        )
        self.assertNotIn("WHERE", conn.last_sql)

    def test_count_persons_with_name_id(self) -> None:
        conn = _FakeDuckDBConnection((3,))
        items_found_repository.count_persons(
            conn,  # type: ignore[arg-type]
            name_id="nm0000209",
        )
        self.assertIn("nu.nconst = ?", conn.last_sql)
        self.assertIn("nm0000209", conn.last_params)

    def test_count_persons_with_year_range(self) -> None:
        conn = _FakeDuckDBConnection((7,))
        items_found_repository.count_persons(
            conn,  # type: ignore[arg-type]
            year_from=2000,
            year_to=2020,
        )
        self.assertIn("CAST(tb.startYear AS INTEGER) >= ?", conn.last_sql)
        self.assertIn("CAST(tb.startYear AS INTEGER) <= ?", conn.last_sql)
        self.assertIn(2000, conn.last_params)
        self.assertIn(2020, conn.last_params)

    def test_count_persons_with_genre(self) -> None:
        conn = _FakeDuckDBConnection((2,))
        items_found_repository.count_persons(
            conn,  # type: ignore[arg-type]
            top_rated=True,
            genre="Drama",
        )
        self.assertIn(
            "list_contains(string_split(lower(COALESCE(tb.genres, '')), ','), lower(?))",
            conn.last_sql,
        )
        self.assertIn("top_rated_titles", conn.last_sql)
        self.assertIn("Drama", conn.last_params)


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class ItemsFoundServiceTests(unittest.TestCase):
    def test_get_items_found_calls_both_count_functions(self) -> None:
        conn = _FakeDuckDBConnection()
        params = ItemsFoundParams(topRated=True, genre="Action")

        with (
            patch.object(
                items_found_repository, "count_titles", return_value=100
            ) as mock_titles,
            patch.object(
                items_found_repository, "count_persons", return_value=200
            ) as mock_persons,
        ):
            result = items_found_service.get_items_found(conn, params)  # type: ignore[arg-type]

        mock_titles.assert_called_once()
        mock_persons.assert_called_once()
        titles_kwargs = mock_titles.call_args.kwargs
        persons_kwargs = mock_persons.call_args.kwargs
        self.assertTrue(titles_kwargs["top_rated"])
        self.assertTrue(persons_kwargs["top_rated"])
        self.assertFalse(titles_kwargs["most_popular"])
        self.assertFalse(persons_kwargs["most_popular"])
        self.assertEqual(titles_kwargs["genre"], "Action")
        self.assertEqual(persons_kwargs["genre"], "Action")

    def test_get_items_found_response_shape(self) -> None:
        conn = _FakeDuckDBConnection()
        params = ItemsFoundParams()

        with (
            patch.object(items_found_repository, "count_titles", return_value=4821),
            patch.object(items_found_repository, "count_persons", return_value=12043),
        ):
            result = items_found_service.get_items_found(conn, params)  # type: ignore[arg-type]

        self.assertIsInstance(result, ItemsFoundResponse)
        self.assertEqual(result.totalTitles, 4821)
        self.assertEqual(result.totalPersons, 12043)

    def test_get_items_found_default_flags(self) -> None:
        conn = _FakeDuckDBConnection()
        params = ItemsFoundParams()

        with (
            patch.object(
                items_found_repository, "count_titles", return_value=0
            ) as mock_titles,
            patch.object(items_found_repository, "count_persons", return_value=0),
        ):
            items_found_service.get_items_found(conn, params)  # type: ignore[arg-type]

        self.assertFalse(mock_titles.call_args.kwargs["top_rated"])
        self.assertFalse(mock_titles.call_args.kwargs["most_popular"])


if __name__ == "__main__":
    unittest.main()
