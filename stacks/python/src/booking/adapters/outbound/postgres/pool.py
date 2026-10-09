"""The asyncpg connection pool, from bootstrap settings."""

from __future__ import annotations

import json

import asyncpg


async def create_pool(dsn: str, size: int) -> asyncpg.Pool:
    async def init_connection(conn: asyncpg.Connection) -> None:
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    return await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=size,
        init=init_connection,
        command_timeout=30,
    )
