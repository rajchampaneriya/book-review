"""An in-memory BookingStore for unit tests.

Mirrors the Postgres adapter's semantics: the key claim is unique, the result is
written in the same transaction, and a failed transaction leaves nothing behind
(the pending writes are only merged into the store on a clean exit).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace

from booking.application.ports.outbound import (
    KeyAlreadyClaimedError,
    StoredKey,
)
from booking.domain.booking import Booking, Charge


class _InMemoryTransaction:
    def __init__(self, store: "InMemoryBookingStore") -> None:
        self._store = store
        self._keys: dict[str, StoredKey] = {}
        self._bookings: list[Booking] = []
        self._charges: list[Charge] = []

    async def claim_key(self, key: str, request_hash: str) -> None:
        if key in self._store.keys or key in self._keys:
            raise KeyAlreadyClaimedError(key)
        self._keys[key] = StoredKey(key, request_hash, None)

    async def add_booking(self, booking: Booking) -> None:
        self._bookings.append(booking)

    async def add_charge(self, charge: Charge) -> None:
        self._charges.append(charge)

    async def store_result(self, key: str, result: dict[str, str]) -> None:
        self._keys[key] = replace(self._keys[key], result=dict(result))

    def commit(self) -> None:
        self._store.keys.update(self._keys)
        self._store.bookings.extend(self._bookings)
        self._store.charges.extend(self._charges)


class InMemoryBookingStore:
    def __init__(self) -> None:
        self.keys: dict[str, StoredKey] = {}
        self.bookings: list[Booking] = []
        self.charges: list[Charge] = []

    async def find_key(self, key: str) -> StoredKey | None:
        return self.keys.get(key)

    @asynccontextmanager
    async def transaction(self):
        tx = _InMemoryTransaction(self)
        yield tx  # an exception in the body rolls back: nothing is merged
        tx.commit()
