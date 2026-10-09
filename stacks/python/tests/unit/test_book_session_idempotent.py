import asyncio

from booking.application.ports.inbound import (
    BookSessionCommand,
    Conflict,
    Created,
    InFlight,
    Replayed,
)
from booking.application.ports.outbound import StoredKey
from booking.application.services.book_session_idempotent import BookSessionIdempotentService
from booking.application.services.request_hash import request_hash
from fakes import InMemoryBookingStore


def command(deposit_cents=2500):
    return BookSessionCommand("r1-000123", "s-42", "d-7", "o-9", deposit_cents)


def test_first_call_creates_one_booking_and_one_charge():
    async def scenario():
        store = InMemoryBookingStore()
        service = BookSessionIdempotentService(store)
        outcome = await service.book("k1", command())
        assert isinstance(outcome, Created)
        assert outcome.confirmation.status == "confirmed"
        assert len(store.bookings) == 1
        assert len(store.charges) == 1
        assert store.keys["k1"].result is not None
        assert store.keys["k1"].request_hash == request_hash(command())

    asyncio.run(scenario())


def test_same_key_and_body_replays_without_new_writes():
    async def scenario():
        store = InMemoryBookingStore()
        service = BookSessionIdempotentService(store)
        first = await service.book("k1", command())
        second = await service.book("k1", command())
        assert isinstance(first, Created)
        assert isinstance(second, Replayed)
        assert second.confirmation == first.confirmation
        assert len(store.bookings) == 1
        assert len(store.charges) == 1

    asyncio.run(scenario())


def test_same_key_different_body_is_a_conflict():
    async def scenario():
        store = InMemoryBookingStore()
        service = BookSessionIdempotentService(store)
        await service.book("k1", command(deposit_cents=2500))
        outcome = await service.book("k1", command(deposit_cents=9999))
        assert isinstance(outcome, Conflict)
        assert len(store.bookings) == 1

    asyncio.run(scenario())


def test_claimed_key_without_result_is_in_flight():
    async def scenario():
        store = InMemoryBookingStore()
        store.keys["k1"] = StoredKey("k1", request_hash(command()), None)
        service = BookSessionIdempotentService(store)
        outcome = await service.book("k1", command())
        assert isinstance(outcome, InFlight)
        assert len(store.bookings) == 0

    asyncio.run(scenario())


def test_failed_transaction_leaves_nothing_behind():
    async def scenario():
        store = InMemoryBookingStore()
        store.keys["k1"] = StoredKey("k1", request_hash(command()), None)
        await BookSessionIdempotentService(store).book("k1", command())
        assert store.bookings == []
        assert store.charges == []
        assert len(store.keys) == 1

    asyncio.run(scenario())
