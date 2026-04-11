from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import DuckDBDep
from app.schemas.title import Title
from app.services import title_service
from app.schemas.common import CommonListQueryParams

router = APIRouter()


@router.get("/", response_model=list[Title])
def list_titles(
    duckdb: DuckDBDep,
    params: Annotated[CommonListQueryParams, Depends()],
) -> list[Title]:
    return title_service.get_titles(duckdb, params.limit, params.skip)
