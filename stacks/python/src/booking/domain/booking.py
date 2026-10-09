"""The booking aggregate: DepositAmount, Booking and the simulated Charge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from booking.domain.errors import InvalidDepositError


@dataclass(frozen=True)
class DepositAmount:
    """A positive amount of money in cents."""

    cents: int

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int) or isinstance(self.cents, bool) or self.cents <= 0:
            raise InvalidDepositError(f"deposit_cents must be a positive integer, got {self.cents!r}")


@dataclass(frozen=True)
class Booking:
    id: uuid.UUID
    client_ref: str
    session_id: str
    dog_id: str
    owner_id: str
    deposit: DepositAmount


@dataclass(frozen=True)
class Charge:
    """A simulated charge; there is no payment provider (rule G7)."""

    id: uuid.UUID
    booking_id: uuid.UUID
    client_ref: str
    amount_cents: int
