"""Outcome counter for POST /v2/bookings (platform plan section 3.3).

Counts what the driving port decided for each keyed booking: created,
replayed, conflict or in_flight. Bootstrap hands it an OpenTelemetry counter
when the observability overlay switches telemetry on, and nothing otherwise,
so this adapter imports no telemetry library and the measured matrix pays one
attribute check per request.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from booking.application.ports.inbound import BookingOutcome, Conflict, Created, InFlight, Replayed


class Counter(Protocol):
    def add(self, amount: int, attributes: Mapping[str, str] | None = None) -> None: ...


_OUTCOME_NAMES: dict[type, str] = {
    Created: "created",
    Replayed: "replayed",
    Conflict: "conflict",
    InFlight: "in_flight",
}


def outcome_name(outcome: BookingOutcome) -> str:
    return _OUTCOME_NAMES[type(outcome)]


class OutcomeCounter:
    """Records one booking outcome per call; does nothing without a counter."""

    def __init__(self, counter: Counter | None = None) -> None:
        self._counter = counter

    def record(self, outcome: BookingOutcome) -> None:
        if self._counter is not None:
            self._counter.add(1, {"outcome": outcome_name(outcome)})
