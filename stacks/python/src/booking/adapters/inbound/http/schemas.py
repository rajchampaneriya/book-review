"""Inbound DTOs: explicit Pydantic models, unknown fields rejected (rule G1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_ref: str
    session_id: str
    dog_id: str
    owner_id: str
    deposit_cents: int = Field(strict=True)  # no "2500"-string coercion


class BookingResponse(BaseModel):
    booking_id: str
    charge_id: str
    status: str


class ErrorResponse(BaseModel):
    error: str
