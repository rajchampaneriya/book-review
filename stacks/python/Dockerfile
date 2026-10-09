# Four stages: build, unit, arch, runtime (docs/exp3-spec.md, Infrastructure).
FROM python:3.14-slim AS build
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir ".[dev]"

FROM build AS unit
COPY tests ./tests
RUN PYTHONPATH=/app/src /opt/venv/bin/pytest

FROM build AS arch
# lint-imports --config ../importlinter.toml from src/ (docs/exp3-spec.md, Architecture tests)
COPY importlinter.toml ./
WORKDIR /app/src
RUN PYTHONPATH=/app/src /opt/venv/bin/lint-imports --config ../importlinter.toml

FROM python:3.14-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY src ./src
EXPOSE 8080
# 2 workers x DB_POOL_SIZE 10 = the spec's 20 connections
CMD ["/opt/venv/bin/uvicorn", "booking.bootstrap.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
