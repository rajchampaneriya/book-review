"""BookSessionNaiveService: the control group.

INTENTIONALLY NAIVE BASELINE: no idempotency key, no deduplication, no retries,
no locks, no unique constraints. One transaction: insert the booking, insert the
charge, commit. A retried request creates a second booking and a second charge,
which is exactly what experiment 3 measures. Do not "fix" this.
"""

from __future__ import annotations

import uuid

from booking.application.ports.inbound import BookSessionCommand, BookingConfirmation
from booking.application.ports.outbound import BookingStore
from booking.domain.booking import Booking, Charge, DepositAmount


class BookSessionNaiveService:
    def __init__(self, store: BookingStore) -> None:
        self._store = store

    async def book(self, command: BookSessionCommand) -> BookingConfirmation:
        deposit = DepositAmount(command.deposit_cents)
        booking_id = uuid.uuid4()
        charge_id = uuid.uuid4()
        async with self._store.transaction() as tx:
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
        return BookingConfirmation(str(booking_id), str(charge_id), "confirmed")
