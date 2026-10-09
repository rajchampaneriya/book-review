"""Environment settings for the composition root."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_schema: str
    stack: str
    db_pool_size: int
    fault_injection: str
    fault_hold_ms: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL", "postgresql://wcf:wcf-local@localhost:55432/bookings"),
            db_schema=os.environ.get("DB_SCHEMA", "python"),
            stack=os.environ.get("STACK", "python"),
            db_pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
            fault_injection=os.environ.get("FAULT_INJECTION", ""),
            fault_hold_ms=int(os.environ.get("FAULT_HOLD_MS", "2000")),
        )

    @property
    def fault_enabled(self) -> bool:
        return self.fault_injection == "enabled"
