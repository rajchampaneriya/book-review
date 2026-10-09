"""The fault hook: a transport concern living in the inbound HTTP adapter.

Called after the use case has returned (the commit has happened) and before the
response is written. A no-op unless FAULT_INJECTION=enabled and the request
carries X-Fault: hold-after-commit; then it waits FAULT_HOLD_MS so the client
times out on a booking that is already committed.
"""

from __future__ import annotations

import asyncio

FAULT_HEADER = "x-fault"
HOLD_AFTER_COMMIT = "hold-after-commit"


class FaultHook:
    def __init__(self, enabled: bool, hold_ms: int) -> None:
        self._enabled = enabled
        self._hold_seconds = hold_ms / 1000

    async def after_commit(self, headers) -> None:
        if self._enabled and headers.get(FAULT_HEADER) == HOLD_AFTER_COMMIT:
            await asyncio.sleep(self._hold_seconds)
