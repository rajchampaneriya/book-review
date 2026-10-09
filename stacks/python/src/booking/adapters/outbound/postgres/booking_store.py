"""PostgresBookingStore and its transaction: plain SQL over asyncpg.

Every statement is one transaction (rule G3): the claim, the booking, the
charge and the result all commit or roll back together. A unique violation on
the key claim (SQLSTATE 23505) is translated into the port's
KeyAlreadyClaimedError; no asyncpg exception crosses the port.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import asyncpg

from booking.application.ports.outbound import KeyAlreadyClaimedError, StoredKey
from booking.domain.booking import Booking, Charge


class PostgresBookingTransaction:
    def __init__(self, conn: asyncpg.Connection, schema: str) -> None:
        self._conn = conn
        self._schema = schema

    async def claim_key(self, key: str, request_hash: str) -> None:
        await self._conn.execute(
            f"INSERT INTO {self._schema}.idempotency_keys (key, request_hash) VALUES ($1, $2)",
            key,
            request_hash,
        )

    async def add_booking(self, booking: Booking) -> None:
        await self._conn.execute(
            f"INSERT INTO {self._schema}.bookings (id, client_ref, session_id, dog_id, owner_id, deposit_cents)"
            " VALUES ($1, $2, $3, $4, $5, $6)",
            booking.id,
            booking.client_ref,
            booking.session_id,
            booking.dog_id,
            booking.owner_id,
            booking.deposit.cents,
        )

    async def add_charge(self, charge: Charge) -> None:
        await self._conn.execute(
            f"INSERT INTO {self._schema}.charges (id, booking_id, client_ref, amount_cents)"
            " VALUES ($1, $2, $3, $4)",
            charge.id,
            charge.booking_id,
            charge.client_ref,
            charge.amount_cents,
        )

    async def store_result(self, key: str, result: dict[str, str]) -> None:
        await self._conn.execute(
            f"UPDATE {self._schema}.idempotency_keys SET result = $2 WHERE key = $1",
            key,
            result,
        )


class PostgresBookingStore:
    def __init__(self, pool: asyncpg.Pool, schema: str) -> None:
        self._pool = pool
        self._schema = schema

    async def find_key(self, key: str) -> StoredKey | None:
        row = await self._pool.fetchrow(
            f"SELECT key, request_hash, result FROM {self._schema}.idempotency_keys WHERE key = $1",
            key,
        )
        if row is None:
            return None
        return StoredKey(row["key"], row["request_hash"], row["result"])

    @asynccontextmanager
    async def transaction(self):
        async with self._pool.acquire() as conn:
            try:
                async with conn.transaction():
                    yield PostgresBookingTransaction(conn, self._schema)
            except asyncpg.UniqueViolationError as e:
                if e.sqlstate == "23505":
                    raise KeyAlreadyClaimedError(e.diag.message_detail or "") from e
                raise
