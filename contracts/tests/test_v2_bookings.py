"""Contract tests 3 to 6: the idempotency-keyed endpoint."""

import asyncio
import httpx

from conftest import BASE_URLS, STACK, booking_body, counts


def test_missing_key_is_rejected(client, clean_schema):
    response = client.post("/v2/bookings", json=booking_body("v2-nokey"))
    assert response.status_code == 400
    assert response.json() == {"error": "idempotency_key_required"}


def test_same_key_and_body_replays_one_booking(client, db, clean_schema):
    body = booking_body("v2-replay")
    first = client.post("/v2/bookings", json=body, headers={"Idempotency-Key": "replay-1"})
    second = client.post("/v2/bookings", json=body, headers={"Idempotency-Key": "replay-1"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.headers.get("Idempotent-Replayed") == "true"
    assert first.headers.get("Idempotent-Replayed") is None
    assert second.json() == first.json()

    c = counts(db, clean_schema)
    assert c["bookings_total"] == 1
    assert c["charges_total"] == 1


def test_same_key_with_a_different_body_is_a_conflict(client, db, clean_schema):
    first = client.post(
        "/v2/bookings", json=booking_body("v2-conflict", deposit_cents=2500), headers={"Idempotency-Key": "conflict-1"}
    )
    second = client.post(
        "/v2/bookings", json=booking_body("v2-conflict", deposit_cents=9999), headers={"Idempotency-Key": "conflict-1"}
    )

    assert first.status_code == 201
    assert second.status_code == 422
    assert second.json() == {"error": "idempotency_conflict"}

    c = counts(db, clean_schema)
    assert c["bookings_total"] == 1


def test_twenty_concurrent_duplicates_create_exactly_one_booking(clean_schema, db):
    body = booking_body("v2-concurrent")
    headers = {"Idempotency-Key": "concurrent-1"}

    async def fire() -> list[httpx.Response]:
        async with httpx.AsyncClient(base_url=BASE_URLS[STACK], timeout=30.0) as client:
            requests = [client.post("/v2/bookings", json=body, headers=headers) for _ in range(20)]
            return list(await asyncio.gather(*requests))

    responses = asyncio.run(fire())

    assert all(r.status_code == 201 for r in responses)
    booking_ids = {r.json()["booking_id"] for r in responses}
    assert len(booking_ids) == 1

    c = counts(db, clean_schema)
    assert c["bookings_total"] == 1
    assert c["charges_total"] == 1
