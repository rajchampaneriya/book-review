"""The naive baseline: one transaction, no key, no deduplication.

These tests assert the baseline behaves naively on purpose; a failure here that
says "two bookings for a retried request" is the expected result, not a bug.
"""

import asyncio
import uuid

from booking.application.ports.inbound import BookSessionCommand
from booking.application.services.book_session_naive import BookSessionNaiveService
from fakes import InMemoryBookingStore


def command(client_ref="r1"):
    return BookSessionCommand(client_ref, "s-42", "d-7", "o-9", 2500)


def test_creates_one_booking_and_one_charge_and_confirms():
    async def scenario():
        store = InMemoryBookingStore()
        service = BookSessionNaiveService(store)
        confirmation = await service.book(command())
        assert confirmation.status == "confirmed"
        assert len(store.bookings) == 1
        assert len(store.charges) == 1
        assert str(store.bookings[0].id) == confirmation.booking_id
        assert str(store.charges[0].id) == confirmation.charge_id
        assert store.charges[0].amount_cents == 2500

    asyncio.run(scenario())


def test_a_retried_request_creates_a_second_booking_and_charge():
    async def scenario():
        store = InMemoryBookingStore()
        service = BookSessionNaiveService(store)
        first = await service.book(command())
        second = await service.book(command())
        assert len(store.bookings) == 2
        assert len(store.charges) == 2
        assert first.booking_id != second.booking_id
        assert first.charge_id != second.charge_id
        assert len({b.id for b in store.bookings}) == 2
        assert uuid.UUID(first.booking_id)  # application-generated ids parse as UUIDs

    asyncio.run(scenario())


def test_no_idempotency_keys_are_stored():
    async def scenario():
        store = InMemoryBookingStore()
        await BookSessionNaiveService(store).book(command())
        await BookSessionNaiveService(store).book(command())
        assert store.keys == {}

    asyncio.run(scenario())
