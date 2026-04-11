from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import titles

api_router = APIRouter()
api_router.include_router(titles.router, prefix="/titles", tags=["titles"])
