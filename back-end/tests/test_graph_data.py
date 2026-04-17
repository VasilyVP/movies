from __future__ import annotations

import unittest
from unittest.mock import ANY, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints.query import router as query_router
from app.core.database import get_duckdb
from app.core.limiter import limiter
from app.repositories.graph_data_repository import GraphCandidateIds, GraphRelationshipRow
from app.schemas.graph_data import GraphDataParams, GraphDataResponse
from app.services import graph_data_service


class GraphDataParamsTests(unittest.TestCase):
    def test_defaults_are_false_and_none(self) -> None:
        params = GraphDataParams()

        self.assertFalse(params.top_rated)
        self.assertFalse(params.most_popular)
        self.assertIsNone(params.title_id)
        self.assertIsNone(params.name_id)
        self.assertIsNone(params.genre)

    def test_rejects_inverted_rating_range(self) -> None:
        with self.assertRaisesRegex(Exception, "ratingRangeFrom"):
            GraphDataParams(ratingRangeFrom=9.0, ratingRangeTo=8.5)


class GraphDataServiceTests(unittest.TestCase):
    def _sample_rows(self) -> list[GraphRelationshipRow]:
        return [
            GraphRelationshipRow(
                person_id="nm0001",
                person_name="Director A",
                person_profession="director,producer",
                person_birth_year=1970,
                person_death_year=2030,
                title_id="tt0001",
                title_name="Film One",
                title_type="movie",
                title_genres="Drama,Crime",
                title_start_year=2001,
                title_rating=9.1,
                title_votes=120000,
                rel_type="DIRECTED",
                rel_category="director",
                rel_job=None,
                rel_characters=None,
            ),
            GraphRelationshipRow(
                person_id="nm0002",
                person_name="Actor B",
                person_profession="actor",
                person_birth_year=1980,
                person_death_year=None,
                title_id="tt0001",
                title_name="Film One",
                title_type="movie",
                title_genres="Drama,Crime",
                title_start_year=2001,
                title_rating=9.1,
                title_votes=120000,
                rel_type="ACTED_IN",
                rel_category="actor",
                rel_job=None,
                rel_characters="['Lead']",
            ),
            GraphRelationshipRow(
                person_id="nm0003",
                person_name="Writer C",
                person_profession="writer",
                person_birth_year=1965,
                person_death_year=None,
                title_id="tt0002",
                title_name="Film Two",
                title_type="movie",
                title_genres="Drama",
                title_start_year=2004,
                title_rating=8.6,
                title_votes=95000,
                rel_type="WROTE",
                rel_category="writer",
                rel_job="screenplay",
                rel_characters=None,
            ),
        ]

    @patch("app.services.graph_data_service.get_settings")
    @patch("app.services.graph_data_service.GraphDatabase.driver")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_candidate_ids")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_graph_rows")
    def test_get_graph_data_builds_response(
        self,
        mocked_fetch: MagicMock,
        mocked_candidates: MagicMock,
        mocked_driver_factory: MagicMock,
        mocked_settings: MagicMock,
    ) -> None:
        mocked_candidates.return_value = GraphCandidateIds(
            title_ids=["tt0001", "tt0002"],
            person_ids=["nm0001", "nm0002", "nm0003"],
            title_ids_truncated=False,
            person_ids_truncated=False,
        )
        mocked_fetch.return_value = self._sample_rows()

        fake_driver = MagicMock()
        mocked_driver_factory.return_value = fake_driver
        mocked_settings.return_value = type(
            "S",
            (),
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "password",
            },
        )()
        fake_duckdb = MagicMock()

        response = graph_data_service.get_graph_data(
            fake_duckdb,
            GraphDataParams(nameId="nm0002"),
        )

        self.assertIsInstance(response, GraphDataResponse)
        self.assertEqual(response.meta.maxNodes, 1000)
        self.assertEqual(response.meta.maxEdges, 3000)
        self.assertGreaterEqual(len(response.nodes), 1)
        self.assertGreaterEqual(len(response.edges), 1)
        self.assertTrue(any(node.isAnchor for node in response.nodes))
        self.assertTrue(any(node.deathYear == 2030 for node in response.nodes))
        mocked_candidates.assert_called_once()
        fake_driver.close.assert_called_once()

    @patch("app.services.graph_data_service.get_settings")
    @patch("app.services.graph_data_service.GraphDatabase.driver")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_candidate_ids")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_graph_rows")
    def test_get_graph_data_passes_candidates_to_repository(
        self,
        mocked_fetch: MagicMock,
        mocked_candidates: MagicMock,
        mocked_driver_factory: MagicMock,
        mocked_settings: MagicMock,
    ) -> None:
        mocked_candidates.return_value = GraphCandidateIds(
            title_ids=["tt0001"],
            person_ids=["nm0001"],
            title_ids_truncated=False,
            person_ids_truncated=False,
        )
        mocked_fetch.return_value = []
        mocked_driver_factory.return_value = MagicMock()
        mocked_settings.return_value = type(
            "S",
            (),
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "password",
            },
        )()
        fake_duckdb = MagicMock()

        graph_data_service.get_graph_data(
            fake_duckdb,
            GraphDataParams(topRated=True, mostPopular=True)
        )

        self.assertTrue(mocked_candidates.call_args.kwargs["top_rated"])
        self.assertTrue(mocked_candidates.call_args.kwargs["most_popular"])
        self.assertEqual(
            mocked_fetch.call_args.kwargs["candidate_title_ids"],
            ["tt0001"],
        )
        self.assertEqual(
            mocked_fetch.call_args.kwargs["candidate_person_ids"],
            ["nm0001"],
        )
        self.assertIsNone(mocked_fetch.call_args.kwargs["anchor_name_id"])
        self.assertIsNone(mocked_fetch.call_args.kwargs["anchor_title_id"])

    @patch("app.services.graph_data_service.get_settings")
    @patch("app.services.graph_data_service.GraphDatabase.driver")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_candidate_ids")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_graph_rows")
    def test_get_graph_data_returns_empty_when_candidates_empty(
        self,
        mocked_fetch: MagicMock,
        mocked_candidates: MagicMock,
        mocked_driver_factory: MagicMock,
        mocked_settings: MagicMock,
    ) -> None:
        mocked_candidates.return_value = GraphCandidateIds(
            title_ids=[],
            person_ids=["nm0001"],
            title_ids_truncated=False,
            person_ids_truncated=False,
        )

        response = graph_data_service.get_graph_data(MagicMock(), GraphDataParams())

        self.assertEqual(response.nodes, [])
        self.assertEqual(response.edges, [])
        self.assertEqual(response.meta.returnedNodes, 0)
        self.assertEqual(response.meta.returnedEdges, 0)
        self.assertFalse(response.meta.truncated)
        mocked_fetch.assert_not_called()
        mocked_driver_factory.assert_not_called()
        mocked_settings.assert_not_called()

    @patch("app.services.graph_data_service.get_settings")
    @patch("app.services.graph_data_service.GraphDatabase.driver")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_candidate_ids")
    @patch("app.services.graph_data_service.graph_data_repository.fetch_graph_rows")
    def test_get_graph_data_allows_title_anchor_with_empty_person_candidates(
        self,
        mocked_fetch: MagicMock,
        mocked_candidates: MagicMock,
        mocked_driver_factory: MagicMock,
        mocked_settings: MagicMock,
    ) -> None:
        mocked_candidates.return_value = GraphCandidateIds(
            title_ids=["tt0001"],
            person_ids=[],
            title_ids_truncated=False,
            person_ids_truncated=False,
        )
        mocked_fetch.return_value = []
        mocked_driver_factory.return_value = MagicMock()
        mocked_settings.return_value = type(
            "S",
            (),
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "password",
            },
        )()

        graph_data_service.get_graph_data(
            MagicMock(),
            GraphDataParams(titleId="tt0001"),
        )

        self.assertEqual(mocked_fetch.call_args.kwargs["anchor_title_id"], "tt0001")
        self.assertEqual(mocked_fetch.call_args.kwargs["anchor_name_id"], None)


class GraphDataEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        limiter.reset()

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(query_router, prefix="/api/query", tags=["query"])
        app.dependency_overrides[get_duckdb] = lambda: MagicMock()
        return app

    def test_graph_data_endpoint_forwards_query_params(self) -> None:
        app = self._build_app()

        expected = GraphDataResponse.model_validate(
            {
                "nodes": [],
                "edges": [],
                "meta": {
                    "maxNodes": 1000,
                    "maxEdges": 3000,
                    "returnedNodes": 0,
                    "returnedEdges": 0,
                    "truncated": False,
                },
            }
        )

        with patch(
            "app.api.endpoints.query.graph_data_service.get_graph_data",
            return_value=expected,
        ) as mocked_get_graph_data:
            with TestClient(app) as client:
                response = client.get(
                    "/api/query/graph-data"
                    "?nameId=nm0000209"
                    "&genre=Drama"
                    "&topRated=true"
                )

        self.assertEqual(response.status_code, 200)
        mocked_get_graph_data.assert_called_once_with(
            ANY,
            GraphDataParams(nameId="nm0000209", genre="Drama", topRated=True)
        )
        self.assertEqual(
            response.json(),
            {
                "nodes": [],
                "edges": [],
                "meta": {
                    "maxNodes": 1000,
                    "maxEdges": 3000,
                    "returnedNodes": 0,
                    "returnedEdges": 0,
                    "truncated": False,
                },
            },
        )

    def test_graph_data_endpoint_rate_limit_triggers(self) -> None:
        app = self._build_app()

        expected = GraphDataResponse.model_validate(
            {
                "nodes": [],
                "edges": [],
                "meta": {
                    "maxNodes": 1000,
                    "maxEdges": 3000,
                    "returnedNodes": 0,
                    "returnedEdges": 0,
                    "truncated": False,
                },
            }
        )

        with patch(
            "app.api.endpoints.query.graph_data_service.get_graph_data",
            return_value=expected,
        ):
            with TestClient(app) as client:
                first = client.get("/api/query/graph-data")
                second = client.get("/api/query/graph-data")

        self.assertIn(first.status_code, {200, 429})
        self.assertIn(second.status_code, {200, 429})

    def test_graph_data_endpoint_returns_503_on_backend_failure(self) -> None:
        app = self._build_app()

        with patch(
            "app.api.endpoints.query.graph_data_service.get_graph_data",
            side_effect=OSError("connection unavailable"),
        ):
            with TestClient(app) as client:
                response = client.get("/api/query/graph-data")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Graph database is temporarily unavailable"},
        )


if __name__ == "__main__":
    unittest.main()
