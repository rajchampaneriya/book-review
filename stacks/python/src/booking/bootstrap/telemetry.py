"""OpenTelemetry SDK setup for the observability overlay (platform plan section 3.3).

Off by default. Unless OTEL_SDK_DISABLED is exactly "false", nothing from
OpenTelemetry is imported and the app is the same service the measured matrix
runs (decision D2). `make observe-up` switches it on and supplies the standard
OTEL_* variables (OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT), which the
SDK reads itself.

FastAPI instruments itself: from 0.143 it records server spans, operation spans
and http.server.request.duration through whatever global providers are set, so
this module only sets the providers, instruments asyncpg for the database spans
and builds the outcome counter. Readiness probes are left out of FastAPI's
telemetry (exclude_health_probes, passed to FastAPI by the composition root).

Uvicorn runs several worker processes and each one calls create_app(), so each
worker sets up its own providers. A per-process service.instance.id keeps the
workers' counters apart in the metrics store.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any

from booking.adapters.inbound.http.metrics import OutcomeCounter

# Readiness probes hit /health every few seconds; they are not booking traffic.
HEALTH_PATH = "/health"


def exclude_health_probes(scope: MutableMapping[str, Any]) -> bool:
    return scope.get("path") == HEALTH_PATH


def telemetry_enabled(environ: Mapping[str, str] = os.environ) -> bool:
    return environ.get("OTEL_SDK_DISABLED", "true").strip().lower() == "false"


def _no_shutdown() -> None:
    return None


@dataclass(frozen=True)
class Telemetry:
    outcomes: OutcomeCounter = field(default_factory=OutcomeCounter)
    shutdown: Callable[[], None] = _no_shutdown


def setup_telemetry() -> Telemetry:
    if not telemetry_enabled():
        return Telemetry()

    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Resource.create() adds OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES.
    resource = Resource.create({"service.instance.id": str(uuid.uuid4())})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(meter_provider)

    AsyncPGInstrumentor().instrument()

    counter = metrics.get_meter("booking.adapters.inbound.http").create_counter(
        "booking.outcomes",
        unit="{booking}",
        description="POST /v2/bookings outcomes: created, replayed, conflict, in_flight",
    )

    def shutdown() -> None:
        tracer_provider.shutdown()
        meter_provider.shutdown()

    return Telemetry(outcomes=OutcomeCounter(counter), shutdown=shutdown)
