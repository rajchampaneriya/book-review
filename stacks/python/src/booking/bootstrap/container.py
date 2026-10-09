"""Composition root: pool, store, services, fault hook, FastAPI app.

Frameworks appear only here and in the adapters; the services are wired to the
ports, never the other way round. The pool opens in the lifespan so the app
imports without a database.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from booking.adapters.inbound.http import error_handlers, health, routes_naive, routes_v2
from booking.adapters.inbound.http.fault_hook import FaultHook
from booking.adapters.outbound.postgres.booking_store import PostgresBookingStore
from booking.adapters.outbound.postgres.pool import create_pool
from booking.application.services.book_session_idempotent import BookSessionIdempotentService
from booking.application.services.book_session_naive import BookSessionNaiveService
from booking.bootstrap.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = await create_pool(settings.database_url, settings.db_pool_size)
        store = PostgresBookingStore(pool, settings.db_schema)
        app.state.naive_use_case = BookSessionNaiveService(store)
        app.state.idempotent_use_case = BookSessionIdempotentService(store)
        app.state.fault_hook = FaultHook(settings.fault_enabled, settings.fault_hold_ms)
        yield
        await pool.close()

    app = FastAPI(title="wcf-physics booking", lifespan=lifespan)
    error_handlers.register_error_handlers(app)
    app.include_router(health.build_health_router(settings.stack))
    app.include_router(routes_naive.router)
    app.include_router(routes_v2.router)
    return app
