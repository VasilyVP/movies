from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

DUCKDB_PATH = REPO_ROOT / "back-end" / "data" / "imdb.duckdb"
SQLITE_PATH = REPO_ROOT / "data" / "chroma_seed.sqlite"

COLLECTION_NAME = "titles"
BATCH_SIZE = 10
TEXT_GENERATION_PROVIDER = "vLLM Python package"

TEXT_GENERATION_MODEL = os.getenv("TEXT_GENERATION_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
HUMAN_MAX_TOKENS = 200
EMBEDDING_MAX_TOKENS = 250

MAX_RETRIES = 3
MAX_CONSECUTIVE_TITLE_FAILURES = 10


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    duckdb_path: Path
    sqlite_path: Path
    collection_name: str
    batch_size: int
    limit: int | None
    text_generation_provider: str
    model: str
    human_max_tokens: int
    embedding_max_tokens: int
    max_retries: int
    max_consecutive_title_failures: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed ChromaDB with IMDB movie descriptions from DuckDB."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Records per batch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for development/testing.",
    )
    return parser


def load_runtime_config(batch_size: int, limit: int | None) -> RuntimeConfig:
    return RuntimeConfig(
        duckdb_path=DUCKDB_PATH,
        sqlite_path=SQLITE_PATH,
        collection_name=COLLECTION_NAME,
        batch_size=batch_size,
        limit=limit,
        text_generation_provider=TEXT_GENERATION_PROVIDER,
        model=TEXT_GENERATION_MODEL,
        human_max_tokens=HUMAN_MAX_TOKENS,
        embedding_max_tokens=EMBEDDING_MAX_TOKENS,
        max_retries=MAX_RETRIES,
        max_consecutive_title_failures=MAX_CONSECUTIVE_TITLE_FAILURES,
    )
