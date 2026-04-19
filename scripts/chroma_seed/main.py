from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable, Protocol

import duckdb

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.chroma_seed.chroma_writer import ChromaWriter
    from scripts.chroma_seed.config import build_parser, load_runtime_config
    from scripts.chroma_seed.duckdb_reader import count_eligible_titles, fetch_title_batch
    from scripts.chroma_seed.llm_client import TextGenerationClient
    from scripts.chroma_seed.models import ChromaSeedRecord, TitleRecord
    from scripts.chroma_seed.progress import (
        ProgressSnapshot,
        create_batch_progress,
        create_overall_progress,
        render_runtime_stats,
    )
    from scripts.chroma_seed.sqlite_store import SQLiteStore
else:
    from .chroma_writer import ChromaWriter
    from .config import build_parser, load_runtime_config
    from .duckdb_reader import count_eligible_titles, fetch_title_batch
    from .llm_client import TextGenerationClient
    from .models import ChromaSeedRecord, TitleRecord
    from .progress import (
        ProgressSnapshot,
        create_batch_progress,
        create_overall_progress,
        render_runtime_stats,
    )
    from .sqlite_store import SQLiteStore


class _UpdatableProgress(Protocol):
    def update(self, n: int = 1) -> object: ...


def main() -> None:
    args = build_parser().parse_args()
    config = load_runtime_config(batch_size=args.batch_size, limit=args.limit)

    try:
        duckdb_connection = duckdb.connect(str(config.duckdb_path), read_only=True)
    except duckdb.Error as exc:
        print(f"Failed to open DuckDB at {config.duckdb_path}: {exc}", flush=True)
        raise SystemExit(1) from exc

    store = SQLiteStore(config.sqlite_path)
    store.initialize_schema()

    reset_requested = _should_reset_existing_state(store)
    if reset_requested:
        store.clear_all()

    resume_title_id = None if reset_requested else store.get_last_success_title_id()

    try:
        writer = ChromaWriter(
            collection_name=config.collection_name,
            max_retries=config.max_retries,
        )
        writer.ensure_collection(reset=reset_requested)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to initialize ChromaDB: {exc}", flush=True)
        raise SystemExit(1) from exc

    generation_client = TextGenerationClient(
        model=config.model,
        max_retries=config.max_retries,
        human_max_tokens=config.human_max_tokens,
        embedding_max_tokens=config.embedding_max_tokens,
    )

    total_available = count_eligible_titles(
        duckdb_connection,
        after_title_id=resume_title_id,
    )
    total_target = min(total_available, config.limit) if config.limit else total_available

    print(
        f"Seeding collection '{config.collection_name}' with {total_target} titles.",
        flush=True,
    )

    start_time = time.perf_counter()
    processed = 0
    success = 0
    failed = 0
    consecutive_failed_titles = 0
    stop_reason: str | None = None

    overall_bar = create_overall_progress(total=total_target)
    batch_bar = create_batch_progress()

    try:
        while processed < total_target:
            remaining = total_target - processed
            current_batch_size = min(config.batch_size, remaining)
            titles = fetch_title_batch(
                duckdb_connection,
                batch_size=current_batch_size,
                after_title_id=resume_title_id,
            )
            if not titles:
                break

            batch_bar.reset(total=len(titles))
            batch_bar.set_description("Batch")

            human_descriptions, human_error = _generate_batch_descriptions(
                generation_client.generate_human_descriptions,
                titles,
            )
            if human_error is not None:
                processed, failed, consecutive_failed_titles = _record_batch_failure(
                    store=store,
                    titles=titles,
                    phase="human_generation",
                    attempt=config.max_retries,
                    error_message=str(human_error),
                    processed=processed,
                    failed=failed,
                    consecutive_failed_titles=consecutive_failed_titles,
                    overall_bar=overall_bar,
                    batch_bar=batch_bar,
                )
                resume_title_id = titles[-1].title_id
                if consecutive_failed_titles >= config.max_consecutive_title_failures:
                    stop_reason = (
                        "Stopped due to consecutive title failure threshold "
                        f"({config.max_consecutive_title_failures})."
                    )
                    break
                continue

            embedding_descriptions, embedding_error = _generate_batch_descriptions(
                generation_client.generate_embedding_descriptions,
                titles,
            )
            if embedding_error is not None:
                processed, failed, consecutive_failed_titles = _record_batch_failure(
                    store=store,
                    titles=titles,
                    phase="embedding_generation",
                    attempt=config.max_retries,
                    error_message=str(embedding_error),
                    processed=processed,
                    failed=failed,
                    consecutive_failed_titles=consecutive_failed_titles,
                    overall_bar=overall_bar,
                    batch_bar=batch_bar,
                )
                resume_title_id = titles[-1].title_id
                if consecutive_failed_titles >= config.max_consecutive_title_failures:
                    stop_reason = (
                        "Stopped due to consecutive title failure threshold "
                        f"({config.max_consecutive_title_failures})."
                    )
                    break
                continue

            records = _combine_batch_records(
                titles=titles,
                human_descriptions=human_descriptions,
                embedding_descriptions=embedding_descriptions,
            )

            try:
                writer.upsert_batch(records)
            except Exception as exc:  # noqa: BLE001
                processed, failed, consecutive_failed_titles = _record_batch_failure(
                    store=store,
                    titles=titles,
                    phase="chroma_write",
                    attempt=config.max_retries,
                    error_message=str(exc),
                    processed=processed,
                    failed=failed,
                    consecutive_failed_titles=consecutive_failed_titles,
                    overall_bar=overall_bar,
                    batch_bar=batch_bar,
                )
                resume_title_id = titles[-1].title_id
                if consecutive_failed_titles >= config.max_consecutive_title_failures:
                    stop_reason = (
                        "Stopped due to consecutive title failure threshold "
                        f"({config.max_consecutive_title_failures})."
                    )
                    break
                continue

            for record in records:
                store.upsert_success(
                    title_id=record.title_id,
                    title=record.title,
                    start_year=record.start_year,
                    human_description=record.human_description,
                    embedding_description=record.embedding_description,
                )

            processed += len(records)
            success += len(records)
            consecutive_failed_titles = 0
            overall_bar.update(len(records))
            batch_bar.update(len(records))
            resume_title_id = records[-1].title_id
    finally:
        overall_bar.close()
        batch_bar.close()
        duckdb_connection.close()

    elapsed = time.perf_counter() - start_time
    summary_counts = store.get_summary_counts()
    snapshot = ProgressSnapshot(
        processed=processed,
        total=total_target,
        success=success,
        failed=failed,
        elapsed_seconds=elapsed,
    )

    print(render_runtime_stats(snapshot), flush=True)
    print(
        (
            "final_state="
            f"processed:{processed}/{total_target} "
            f"success:{summary_counts.success_count} "
            f"failed:{summary_counts.failed_count}"
        ),
        flush=True,
    )

    if stop_reason is not None:
        print(stop_reason, flush=True)
        raise SystemExit(1)


def _should_reset_existing_state(store: SQLiteStore) -> bool:
    if not store.has_records():
        return False

    if not sys.stdin.isatty():
        return False

    while True:
        choice = input(
            "Existing SQLite state found. Continue from last success or restart? [c/r]: "
        ).strip().lower()
        if choice in {"c", "continue", ""}:
            return False
        if choice in {"r", "restart"}:
            return True
        print("Please answer with 'c' to continue or 'r' to restart.", flush=True)


def _generate_batch_descriptions(
    generator: Callable[[list[TitleRecord]], dict[str, str]],
    titles: list[TitleRecord],
) -> tuple[dict[str, str], Exception | None]:
    try:
        return generator(titles), None
    except Exception as exc:  # noqa: BLE001
        return {}, exc


def _combine_batch_records(
    titles: list[TitleRecord],
    human_descriptions: dict[str, str],
    embedding_descriptions: dict[str, str],
) -> list[ChromaSeedRecord]:
    records: list[ChromaSeedRecord] = []
    for title in titles:
        records.append(
            ChromaSeedRecord(
                title_id=title.title_id,
                title=title.title,
                start_year=title.start_year,
                human_description=human_descriptions[title.title_id],
                embedding_description=embedding_descriptions[title.title_id],
            )
        )
    return records


def _record_batch_failure(
    store: SQLiteStore,
    titles: list[TitleRecord],
    phase: str,
    attempt: int,
    error_message: str,
    processed: int,
    failed: int,
    consecutive_failed_titles: int,
    overall_bar: _UpdatableProgress,
    batch_bar: _UpdatableProgress,
) -> tuple[int, int, int]:
    for title in titles:
        store.mark_failed(
            title_id=title.title_id,
            title=title.title,
            start_year=title.start_year,
            phase=phase,
            attempt=attempt,
            error_message=error_message,
        )

    processed += len(titles)
    failed += len(titles)
    consecutive_failed_titles += len(titles)
    overall_bar.update(len(titles))
    batch_bar.update(len(titles))
    return processed, failed, consecutive_failed_titles


if __name__ == "__main__":
    main()
