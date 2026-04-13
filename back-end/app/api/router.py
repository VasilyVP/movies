from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import query

api_router = APIRouter()
api_router.include_router(query.router, prefix="/query", tags=["Query"])
