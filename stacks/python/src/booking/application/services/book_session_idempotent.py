"""BookSessionIdempotentService: claim the key, book, store the result.

G2 policy in one transaction: claim the idempotency key (unique), create the
booking and the charge, store the result in the key row, commit. If the key is
already claimed, roll back, then read the key row outside the failed
transaction: a different hash is a Conflict, a stored result is a Replay, a
claimed key with no result is InFlight (which should be impossible after a
commit and is logged as a bug).
"""

from __future__ import annotations

import logging
import uuid

from booking.application.ports.inbound import (
    BookSessionCommand,
    BookingConfirmation,
    BookingOutcome,
    Conflict,
    Created,
    InFlight,
    Replayed,
)
from booking.application.ports.outbound import BookingStore, KeyAlreadyClaimedError
from booking.application.services.request_hash import request_hash
from booking.domain.booking import Booking, Charge, DepositAmount

logger = logging.getLogger(__name__)


class BookSessionIdempotentService:
    def __init__(self, store: BookingStore) -> None:
        self._store = store

    async def book(self, key: str, command: BookSessionCommand) -> BookingOutcome:
        request = request_hash(command)
        deposit = DepositAmount(command.deposit_cents)
        booking_id = uuid.uuid4()
        charge_id = uuid.uuid4()
        result = {
            "booking_id": str(booking_id),
            "charge_id": str(charge_id),
            "status": "confirmed",
        }
        try:
            async with self._store.transaction() as tx:
                await tx.claim_key(key, request)
                await tx.add_booking(
                    Booking(
                        id=booking_id,
                        client_ref=command.client_ref,
                        session_id=command.session_id,
                        dog_id=command.dog_id,
                        owner_id=command.owner_id,
                        deposit=deposit,
                    )
                )
                await tx.add_charge(
                    Charge(
                        id=charge_id,
                        booking_id=booking_id,
                        client_ref=command.client_ref,
                        amount_cents=deposit.cents,
                    )
                )
                await tx.store_result(key, result)
        except KeyAlreadyClaimedError:
            stored = await self._store.find_key(key)
            if stored is None or stored.request_hash != request:
                return Conflict(key)
            if stored.result is not None:
                confirmation = BookingConfirmation(
                    booking_id=stored.result["booking_id"],
                    charge_id=stored.result["charge_id"],
                    status=stored.result["status"],
                )
                return Replayed(confirmation)
            logger.error(
                "idempotency key %s is claimed with no result after a commit; "
                "should be impossible (InFlight returned)",
                key,
            )
            return InFlight(key)
        return Created(BookingConfirmation(result["booking_id"], result["charge_id"], result["status"]))
