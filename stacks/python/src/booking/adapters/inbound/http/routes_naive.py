"""POST /naive/bookings: the control-group endpoint.

INTENTIONALLY NAIVE BASELINE: no idempotency key, no deduplication, no retries,
no locks. A retried request creates a second booking and a second charge, which
is exactly what experiment 3 measures. Do not "fix" this.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from booking.adapters.inbound.http.fault_hook import FaultHook
from booking.adapters.inbound.http.schemas import BookingRequest, BookingResponse
from booking.application.ports.inbound import BookSessionCommand, BookSessionNaiveUseCase

router = APIRouter()


def _use_case(request: Request) -> BookSessionNaiveUseCase:
    return request.app.state.naive_use_case


def _fault_hook(request: Request) -> FaultHook:
    return request.app.state.fault_hook


@router.post("/naive/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking: BookingRequest,
    request: Request,
    use_case: BookSessionNaiveUseCase = Depends(_use_case),
    fault_hook: FaultHook = Depends(_fault_hook),
) -> BookingResponse:
    confirmation = await use_case.book(
        BookSessionCommand(
            client_ref=booking.client_ref,
            session_id=booking.session_id,
            dog_id=booking.dog_id,
            owner_id=booking.owner_id,
            deposit_cents=booking.deposit_cents,
        )
    )
    await fault_hook.after_commit(request.headers)
    return BookingResponse(
        booking_id=confirmation.booking_id,
        charge_id=confirmation.charge_id,
        status=confirmation.status,
    )
