from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tqdm import tqdm


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    processed: int
    total: int
    success: int
    failed: int
    elapsed_seconds: float


def create_overall_progress(total: int) -> tqdm[Any]:
    return tqdm(total=total, desc="Total", unit="title")


def create_batch_progress() -> tqdm[Any]:
    return tqdm(total=0, desc="Batch", unit="title", leave=False)


def render_runtime_stats(snapshot: ProgressSnapshot) -> str:
    avg = snapshot.elapsed_seconds / snapshot.processed if snapshot.processed else 0.0
    return (
        f"processed={snapshot.processed}/{snapshot.total} "
        f"success={snapshot.success} failed={snapshot.failed} "
        f"avg_sec_per_title={avg:.2f} elapsed_sec={snapshot.elapsed_seconds:.2f}"
    )
