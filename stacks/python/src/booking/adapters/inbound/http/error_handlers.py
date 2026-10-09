"""Status-code mapping: adapter-level errors to the spec's error bodies."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from booking.domain.errors import InvalidDepositError


class IdempotencyKeyRequired(Exception):
    """The Idempotency-Key header is missing or not 1-255 printable ASCII characters."""


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "invalid_request"})

    @app.exception_handler(InvalidDepositError)
    async def invalid_deposit(request: Request, exc: InvalidDepositError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "invalid_request"})

    @app.exception_handler(IdempotencyKeyRequired)
    async def idempotency_key_required(request: Request, exc: IdempotencyKeyRequired) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "idempotency_key_required"})
