from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .models import SummaryCounts


class SQLiteStore:
    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path

    def initialize_schema(self) -> None:
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seed_records (
                    title_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_year INTEGER,
                    human_description TEXT,
                    embedding_description TEXT,
                    status TEXT NOT NULL,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seed_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def has_records(self) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) FROM seed_records").fetchone()
        return bool(row and int(row[0]) > 0)

    def clear_all(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM seed_failures")
            connection.execute("DELETE FROM seed_records")
            connection.commit()

    def get_last_success_title_id(self) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT MAX(title_id) FROM seed_records WHERE status = 'success'"
            ).fetchone()
        if row is None:
            return None
        return row[0]

    def upsert_success(
        self,
        title_id: str,
        title: str,
        start_year: int,
        human_description: str,
        embedding_description: str,
    ) -> None:
        now = _utc_now_iso()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO seed_records (
                    title_id,
                    title,
                    start_year,
                    human_description,
                    embedding_description,
                    status,
                    last_error,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, 'success', NULL, ?)
                ON CONFLICT(title_id) DO UPDATE SET
                    title = excluded.title,
                    start_year = excluded.start_year,
                    human_description = excluded.human_description,
                    embedding_description = excluded.embedding_description,
                    status = 'success',
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    title_id,
                    title,
                    start_year,
                    human_description,
                    embedding_description,
                    now,
                ),
            )
            connection.commit()

    def mark_failed(
        self,
        title_id: str,
        title: str,
        start_year: int,
        phase: str,
        attempt: int,
        error_message: str,
    ) -> None:
        now = _utc_now_iso()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO seed_records (
                    title_id,
                    title,
                    start_year,
                    human_description,
                    embedding_description,
                    status,
                    last_error,
                    updated_at
                ) VALUES (?, ?, ?, NULL, NULL, 'failed', ?, ?)
                ON CONFLICT(title_id) DO UPDATE SET
                    title = excluded.title,
                    start_year = excluded.start_year,
                    status = 'failed',
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (title_id, title, start_year, error_message, now),
            )
            connection.execute(
                """
                INSERT INTO seed_failures (title_id, phase, attempt, error_message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title_id, phase, attempt, error_message, now),
            )
            connection.commit()

    def get_summary_counts(self) -> SummaryCounts:
        with closing(self._connect()) as connection:
            success_row = connection.execute(
                "SELECT COUNT(*) FROM seed_records WHERE status = 'success'"
            ).fetchone()
            failed_row = connection.execute(
                "SELECT COUNT(*) FROM seed_records WHERE status = 'failed'"
            ).fetchone()

        return SummaryCounts(
            success_count=int(success_row[0]) if success_row is not None else 0,
            failed_count=int(failed_row[0]) if failed_row is not None else 0,
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._sqlite_path)


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
