"""Uvicorn entry point: booking.bootstrap.main:app."""

from booking.bootstrap.container import create_app

app = create_app()
