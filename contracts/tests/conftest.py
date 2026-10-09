"""STACK selects the base URL and the Postgres schema; both come from the
cluster the harness already runs: NodePorts on localhost, Postgres at
localhost:55432 with the local-development credentials."""

from __future__ import annotations

import os

import httpx
import psycopg
import pytest

STACK = os.environ.get("STACK", "python")
BASE_URLS = {"dotnet": "http://localhost:8081", "java": "http://localhost:8082", "python": "http://localhost:8083"}
DB_HOST = "localhost"
DB_PORT = 55432
DB_USER = "wcf"
DB_PASSWORD = "wcf-local"
DB_NAME = "bookings"


@pytest.fixture()
def base_url() -> str:
    return BASE_URLS[STACK]


@pytest.fixture()
def client(base_url: str) -> httpx.Client:
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client


@pytest.fixture()
def db() -> psycopg.Connection:
    with psycopg.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME) as conn:
        yield conn


@pytest.fixture()
def clean_schema(db: psycopg.Connection):
    """Start every test from empty tables, and count only in the database."""
    with db.cursor() as cur:
        cur.execute(f"TRUNCATE {STACK}.bookings, {STACK}.charges, {STACK}.idempotency_keys")
    db.commit()
    yield STACK


def counts(db: psycopg.Connection, stack: str) -> dict[str, int]:
    with db.cursor() as cur:
        cur.execute(
            f"SELECT count(*), count(DISTINCT client_ref) FROM {stack}.bookings"
        )
        bookings_total, bookings_distinct = cur.fetchone()
        cur.execute(
            f"SELECT count(*), count(DISTINCT client_ref) FROM {stack}.charges"
        )
        charges_total, charges_distinct = cur.fetchone()
    return {
        "bookings_total": bookings_total,
        "bookings_distinct": bookings_distinct,
        "charges_total": charges_total,
        "charges_distinct": charges_distinct,
        "duplicate_bookings": bookings_total - bookings_distinct,
        "duplicate_charges": charges_total - charges_distinct,
    }


def booking_body(client_ref: str, deposit_cents: int = 2500) -> dict:
    return {
        "client_ref": client_ref,
        "session_id": "s-42",
        "dog_id": "d-7",
        "owner_id": "o-9",
        "deposit_cents": deposit_cents,
    }
