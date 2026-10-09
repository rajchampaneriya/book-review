"""GET /health: the liveness probe."""

from __future__ import annotations

from fastapi import APIRouter


def build_health_router(stack: str) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "stack": stack}

    return router
