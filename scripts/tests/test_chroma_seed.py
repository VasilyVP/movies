from __future__ import annotations

import sqlite3
import types
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import cast
from unittest.mock import patch

import duckdb

_REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.chroma_seed.duckdb_reader import (  # noqa: E402
    count_eligible_titles,
    fetch_title_batch,
)
from scripts.chroma_seed.llm_client import TextGenerationClient  # noqa: E402
from scripts.chroma_seed.models import TitleRecord  # noqa: E402
from scripts.chroma_seed.config import load_runtime_config  # noqa: E402
from scripts.chroma_seed.sqlite_store import SQLiteStore  # noqa: E402


class SQLiteStoreTests(unittest.TestCase):
    def test_initialize_creates_required_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = Path(temp_dir) / "seed.sqlite"
            store = SQLiteStore(sqlite_path)
            store.initialize_schema()

            with closing(sqlite3.connect(sqlite_path)) as connection:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()

            table_names = {row[0] for row in rows}
            self.assertIn("seed_records", table_names)
            self.assertIn("seed_failures", table_names)

    def test_last_successful_title_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = Path(temp_dir) / "seed.sqlite"
            store = SQLiteStore(sqlite_path)
            store.initialize_schema()

            store.upsert_success(
                title_id="tt0000002",
                title="Second",
                start_year=2001,
                human_description="Human",
                embedding_description="Embedding",
            )
            store.upsert_success(
                title_id="tt0000010",
                title="Tenth",
                start_year=2002,
                human_description="Human",
                embedding_description="Embedding",
            )

            self.assertEqual(store.get_last_success_title_id(), "tt0000010")

    def test_failed_title_is_persisted_with_failure_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = Path(temp_dir) / "seed.sqlite"
            store = SQLiteStore(sqlite_path)
            store.initialize_schema()

            store.mark_failed(
                title_id="tt1234567",
                title="Failure Case",
                start_year=1999,
                phase="human_generation",
                attempt=3,
                error_message="generation failed",
            )

            summary = store.get_summary_counts()
            self.assertEqual(summary.success_count, 0)
            self.assertEqual(summary.failed_count, 1)

            with closing(sqlite3.connect(sqlite_path)) as connection:
                failure_rows = connection.execute(
                    "SELECT title_id, phase, attempt, error_message FROM seed_failures"
                ).fetchall()

            self.assertEqual(len(failure_rows), 1)
            self.assertEqual(
                failure_rows[0],
                ("tt1234567", "human_generation", 3, "generation failed"),
            )


class DuckDBReaderTests(unittest.TestCase):
    def test_count_and_fetch_apply_spec_filters_and_ordering(self) -> None:
        connection = duckdb.connect(database=":memory:")
        connection.execute(
            """
            CREATE TABLE title_basics (
                tconst TEXT,
                titleType TEXT,
                primaryTitle TEXT,
                startYear INTEGER
            );
            """
        )
        connection.execute(
            """
            CREATE TABLE title_ratings (
                tconst TEXT,
                averageRating DOUBLE,
                numVotes INTEGER
            );
            """
        )

        connection.execute(
            """
            INSERT INTO title_basics VALUES
                ('tt0000001', 'movie', 'A Movie', 1995),
                ('tt0000002', 'movie', 'B Movie', 2000),
                ('tt0000003', 'tvSeries', 'Series', 2001),
                ('tt0000004', 'movie', 'Old Movie', 1980),
                ('tt0000005', 'movie', 'Recent Movie', 2024),
                ('tt0000006', 'movie', 'Low Rated', 2005);
            """
        )
        connection.execute(
            """
            INSERT INTO title_ratings VALUES
                ('tt0000001', 8.0, 1000),
                ('tt0000002', 7.6, 1000),
                ('tt0000003', 9.0, 1000),
                ('tt0000004', 8.5, 1000),
                ('tt0000005', 8.7, 1000),
                ('tt0000006', 7.4, 1000);
            """
        )

        self.assertEqual(count_eligible_titles(connection), 2)

        rows = fetch_title_batch(connection, batch_size=10, after_title_id=None)
        self.assertEqual([row.title_id for row in rows], ["tt0000001", "tt0000002"])

        resumed_rows = fetch_title_batch(
            connection,
            batch_size=10,
            after_title_id="tt0000001",
        )
        self.assertEqual([row.title_id for row in resumed_rows], ["tt0000002"])


class RuntimeConfigTests(unittest.TestCase):
    def test_runtime_config_exposes_vllm_and_token_limits(self) -> None:
        config = load_runtime_config(batch_size=4, limit=8)

        self.assertEqual(config.batch_size, 4)
        self.assertEqual(config.limit, 8)
        self.assertEqual(config.human_max_tokens, 200)
        self.assertEqual(config.embedding_max_tokens, 250)
        self.assertEqual(config.text_generation_provider, "vLLM Python package")


class TextGenerationClientTests(unittest.TestCase):
    def test_generate_human_descriptions_uses_vllm_batch_and_token_limit(self) -> None:
        titles = [
            TitleRecord(title_id="tt0000001", title="Alpha", start_year=2001),
            TitleRecord(title_id="tt0000002", title="Beta", start_year=2002),
        ]

        calls: list[dict[str, object]] = []

        class _FakeSamplingParams:
            def __init__(self, *, temperature: int, max_tokens: int) -> None:
                self.temperature = temperature
                self.max_tokens = max_tokens

        class _FakeGeneratedText:
            def __init__(self, text: str) -> None:
                self.text = text

        class _FakeRequestOutput:
            def __init__(self, text: str) -> None:
                self.outputs = [_FakeGeneratedText(text)]

        class _FakeLLM:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def generate(self, prompts: list[str], sampling_params: object) -> list[object]:
                calls.append(
                    {
                        "prompts": prompts,
                        "sampling_params": sampling_params,
                    }
                )
                return [
                    _FakeRequestOutput("human one"),
                    _FakeRequestOutput("human two"),
                ]

        fake_vllm = types.ModuleType("vllm")
        setattr(fake_vllm, "LLM", _FakeLLM)
        setattr(fake_vllm, "SamplingParams", _FakeSamplingParams)

        with patch.dict(sys.modules, {"vllm": fake_vllm}):
            client = TextGenerationClient(
                model="llama3.2:3b",
                max_retries=3,
                human_max_tokens=200,
                embedding_max_tokens=250,
            )

            actual = client.generate_human_descriptions(titles)

        self.assertEqual(actual, {"tt0000001": "human one", "tt0000002": "human two"})
        self.assertEqual(len(calls), 1)
        prompts = cast(list[str], calls[0]["prompts"])
        self.assertIn("Title: Alpha", str(prompts[0]))
        self.assertIn("Title: Beta", str(prompts[1]))
        sampling_params = calls[0]["sampling_params"]
        self.assertEqual(getattr(sampling_params, "temperature"), 0)
        self.assertEqual(getattr(sampling_params, "max_tokens"), 200)

    def test_generate_embedding_descriptions_uses_embedding_token_limit(self) -> None:
        titles = [
            TitleRecord(title_id="tt0000003", title="Gamma", start_year=2003),
        ]

        observed_max_tokens: list[int] = []

        class _FakeSamplingParams:
            def __init__(self, *, temperature: int, max_tokens: int) -> None:
                self.temperature = temperature
                self.max_tokens = max_tokens

        class _FakeGeneratedText:
            def __init__(self, text: str) -> None:
                self.text = text

        class _FakeRequestOutput:
            def __init__(self, text: str) -> None:
                self.outputs = [_FakeGeneratedText(text)]

        class _FakeLLM:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def generate(self, prompts: list[str], sampling_params: object) -> list[object]:
                observed_max_tokens.append(getattr(sampling_params, "max_tokens"))
                return [_FakeRequestOutput("structured output")]

        fake_vllm = types.ModuleType("vllm")
        setattr(fake_vllm, "LLM", _FakeLLM)
        setattr(fake_vllm, "SamplingParams", _FakeSamplingParams)

        with patch.dict(sys.modules, {"vllm": fake_vllm}):
            client = TextGenerationClient(
                model="llama3.2:3b",
                max_retries=3,
                human_max_tokens=200,
                embedding_max_tokens=250,
            )
            actual = client.generate_embedding_descriptions(titles)

        self.assertEqual(actual, {"tt0000003": "structured output"})
        self.assertEqual(observed_max_tokens, [250])

    def test_retries_and_raises_after_max_retries(self) -> None:
        titles = [
            TitleRecord(title_id="tt0000009", title="Retry", start_year=2009),
        ]

        attempts: list[int] = []

        class _FakeSamplingParams:
            def __init__(self, *, temperature: int, max_tokens: int) -> None:
                self.temperature = temperature
                self.max_tokens = max_tokens

        class _FakeLLM:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def generate(self, prompts: list[str], sampling_params: object) -> list[object]:
                attempts.append(1)
                raise RuntimeError("boom")

        fake_vllm = types.ModuleType("vllm")
        setattr(fake_vllm, "LLM", _FakeLLM)
        setattr(fake_vllm, "SamplingParams", _FakeSamplingParams)

        with patch.dict(sys.modules, {"vllm": fake_vllm}):
            client = TextGenerationClient(
                model="llama3.2:3b",
                max_retries=3,
                human_max_tokens=200,
                embedding_max_tokens=250,
            )

            with self.assertRaises(RuntimeError):
                client.generate_human_descriptions(titles)

        self.assertEqual(len(attempts), 3)

    def test_retries_when_output_missing_or_empty(self) -> None:
        titles = [
            TitleRecord(title_id="tt0000011", title="One", start_year=2011),
            TitleRecord(title_id="tt0000012", title="Two", start_year=2012),
        ]

        calls: list[int] = []

        class _FakeSamplingParams:
            def __init__(self, *, temperature: int, max_tokens: int) -> None:
                self.temperature = temperature
                self.max_tokens = max_tokens

        class _FakeGeneratedText:
            def __init__(self, text: str) -> None:
                self.text = text

        class _FakeRequestOutput:
            def __init__(self, text: str) -> None:
                self.outputs = [_FakeGeneratedText(text)]

        class _FakeLLM:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def generate(self, prompts: list[str], sampling_params: object) -> list[object]:
                calls.append(1)
                if len(calls) == 1:
                    return [_FakeRequestOutput("only one output")]
                if len(calls) == 2:
                    return [_FakeRequestOutput("first"), _FakeRequestOutput("   ")]
                return [_FakeRequestOutput("first"), _FakeRequestOutput("second")]

        fake_vllm = types.ModuleType("vllm")
        setattr(fake_vllm, "LLM", _FakeLLM)
        setattr(fake_vllm, "SamplingParams", _FakeSamplingParams)

        with patch.dict(sys.modules, {"vllm": fake_vllm}):
            client = TextGenerationClient(
                model="llama3.2:3b",
                max_retries=3,
                human_max_tokens=200,
                embedding_max_tokens=250,
            )
            actual = client.generate_human_descriptions(titles)

        self.assertEqual(actual, {"tt0000011": "first", "tt0000012": "second"})
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
