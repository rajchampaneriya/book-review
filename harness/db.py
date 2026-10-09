"""Postgres access for the harness: truncate before a run, count after.

Duplicates are always counted in the database, never inferred from client logs.
"""

from __future__ import annotations

import psycopg

HOST = "localhost"
PORT = 55432
USER = "wcf"
PASSWORD = "wcf-local"
NAME = "bookings"


def connect() -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, dbname=NAME)


def truncate(stack: str) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {stack}.bookings, {stack}.charges, {stack}.idempotency_keys")
    conn.close()


def counts(stack: str) -> dict[str, int]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*), count(DISTINCT client_ref) FROM {stack}.bookings")
        bookings_total, bookings_distinct = cur.fetchone()
        cur.execute(f"SELECT count(*), count(DISTINCT client_ref) FROM {stack}.charges")
        charges_total, charges_distinct = cur.fetchone()
    conn.close()
    return {
        "bookings_total": bookings_total,
        "bookings_distinct": bookings_distinct,
        "duplicate_bookings": bookings_total - bookings_distinct,
        "charges_total": charges_total,
        "duplicate_charges": charges_total - charges_distinct,
    }
