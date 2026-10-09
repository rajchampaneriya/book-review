"""Driving ports: the two use cases, their command, confirmation and outcomes.

The outcomes are the whole G2 policy, in application terms: Created (this call
booked), Replayed (an earlier call with the same key and body booked), Conflict
(same key, different body) and InFlight (claimed but no result; a bug if seen).
HTTP status codes belong to the inbound adapter, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BookSessionCommand:
    client_ref: str
    session_id: str
    dog_id: str
    owner_id: str
    deposit_cents: int


@dataclass(frozen=True)
class BookingConfirmation:
    booking_id: str
    charge_id: str
    status: str


@dataclass(frozen=True)
class Created:
    confirmation: BookingConfirmation


@dataclass(frozen=True)
class Replayed:
    confirmation: BookingConfirmation


@dataclass(frozen=True)
class Conflict:
    key: str


@dataclass(frozen=True)
class InFlight:
    key: str


BookingOutcome = Created | Replayed | Conflict | InFlight


@runtime_checkable
class BookSessionNaiveUseCase(Protocol):
    async def book(self, command: BookSessionCommand) -> BookingConfirmation: ...


@runtime_checkable
class BookSessionIdempotentUseCase(Protocol):
    async def book(self, key: str, command: BookSessionCommand) -> BookingOutcome: ...
