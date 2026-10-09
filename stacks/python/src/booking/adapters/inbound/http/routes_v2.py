"""POST /v2/bookings: the idempotency-keyed endpoint.

The route validates the Idempotency-Key header, calls the driving port, maps
the outcome to a status code (Created/Replayed 201, Conflict 422, InFlight
409) and then runs the fault hook. All policy lives in the application layer;
only transport lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from booking.adapters.inbound.http.error_handlers import IdempotencyKeyRequired
from booking.adapters.inbound.http.fault_hook import FaultHook
from booking.adapters.inbound.http.schemas import BookingRequest, BookingResponse
from booking.application.ports.inbound import (
    BookSessionCommand,
    BookSessionIdempotentUseCase,
    Conflict,
    Created,
    InFlight,
    Replayed,
)

router = APIRouter()

KEY_HEADER = "Idempotency-Key"
PRINTABLE_ASCII = set(range(0x21, 0x7F))  # 1-255 printable ASCII, no space


def _validate_key(key: str | None) -> str:
    if key is None or not (1 <= len(key) <= 255) or any(ord(c) not in PRINTABLE_ASCII for c in key):
        raise IdempotencyKeyRequired()
    return key


def _use_case(request: Request) -> BookSessionIdempotentUseCase:
    return request.app.state.idempotent_use_case


def _fault_hook(request: Request) -> FaultHook:
    return request.app.state.fault_hook


@router.post("/v2/bookings", status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking: BookingRequest,
    request: Request,
    use_case: BookSessionIdempotentUseCase = Depends(_use_case),
    fault_hook: FaultHook = Depends(_fault_hook),
):
    key = _validate_key(request.headers.get(KEY_HEADER))
    command = BookSessionCommand(
        client_ref=booking.client_ref,
        session_id=booking.session_id,
        dog_id=booking.dog_id,
        owner_id=booking.owner_id,
        deposit_cents=booking.deposit_cents,
    )
    outcome = await use_case.book(key, command)
    await fault_hook.after_commit(request.headers)

    if isinstance(outcome, Conflict):
        return JSONResponse(status_code=422, content={"error": "idempotency_conflict"})
    if isinstance(outcome, InFlight):
        return JSONResponse(
            status_code=409,
            content={"error": "idempotency_in_flight"},
            headers={"Retry-After": "1"},
        )

    body = BookingResponse(
        booking_id=outcome.confirmation.booking_id,
        charge_id=outcome.confirmation.charge_id,
        status=outcome.confirmation.status,
    )
    if isinstance(outcome, Replayed):
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=body.model_dump(),
            headers={"Idempotent-Replayed": "true"},
        )
    assert isinstance(outcome, Created)
    return body
