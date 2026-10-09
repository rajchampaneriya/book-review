"""Driven ports: the BookingStore, its transaction, StoredKey and the key error.

The application layer owns the idempotency policy but never sees SQL, Postgres
or driver types: drivers live in the outbound adapters, and SQLSTATE 23505 from
a claim is translated into KeyAlreadyClaimedError at the port boundary.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from booking.domain.booking import Booking, Charge


class KeyAlreadyClaimedError(Exception):
    """The idempotency key is already claimed; the attempted transaction was rolled back."""


@dataclass(frozen=True)
class StoredKey:
    key: str
    request_hash: str
    result: dict[str, str] | None  # {"booking_id": ..., "charge_id": ..., "status": ...}


@runtime_checkable
class BookingTransaction(Protocol):
    async def claim_key(self, key: str, request_hash: str) -> None:
        """Reserve the idempotency key; raises KeyAlreadyClaimedError if taken."""
        ...

    async def add_booking(self, booking: Booking) -> None: ...
    async def add_charge(self, charge: Charge) -> None: ...
    async def store_result(self, key: str, result: dict[str, str]) -> None: ...


@runtime_checkable
class BookingStore(Protocol):
    async def find_key(self, key: str) -> StoredKey | None:
        """Read a key row outside any failed transaction (the replay check)."""
        ...

    def transaction(self) -> AbstractAsyncContextManager[BookingTransaction]:
        """Run one transaction; commit on clean exit, roll back on any error."""
        ...
