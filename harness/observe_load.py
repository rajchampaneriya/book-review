"""make observe-load: light booking traffic so the observability overlay's
dashboard has something to show.

Usage (via make): [STACK=<dotnet|java|python>] [MINUTES=5] python -m harness.observe_load

Not a measurement: nothing is truncated before the run, nothing is written to
results/, and no number from here belongs in an article (rule H1). It is the
dashboard's test pattern. Run make observe-up first, or the stacks receive the
bookings but export nothing.

Every stack that answers on /health gets the same fixed mix, one tick a second.
On tick n (counting from 1), in this order:

  every tick       a new keyed booking            201, outcome created
  every 3rd tick   that same booking again        201, outcome replayed
  every 20th tick  that key with another deposit  422, outcome conflict
  every 30th tick  a booking with no key          400
  every 2nd tick   a naive booking                201 (the control group)

The mix is fixed rather than random so that the BDD scenarios can check the
dashboard's counters against exactly what was sent. The stacks run
concurrently; a stack whose /health does not answer (the matrix scales idle
stacks to 0) is reported as skipped. Bookings carry client_ref values starting
"observe-load-" and stay in the stack's schema until the next exp3 run or
contract test truncates it.

Exits 0 when every running stack answered every request as expected, 1 when a
request failed or got an unexpected status (or no stack answered at all), and
2 on bad arguments. Ctrl-C stops early and prints the counts so far.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field

import httpx

BASE_URLS = {"dotnet": "http://localhost:8081", "java": "http://localhost:8082", "python": "http://localhost:8083"}
STACKS = ("dotnet", "java", "python")
REF_PREFIX = "observe-load"
TICK_SECONDS = 1.0
DEPOSIT_CENTS = 2500
CONFLICT_DEPOSIT_CENTS = 9999

REPLAY_EVERY = 3
CONFLICT_EVERY = 20
MISSING_KEY_EVERY = 30
NAIVE_EVERY = 2

KINDS = ("created", "replayed", "conflict", "missing_key", "naive")


@dataclass(frozen=True)
class Request:
    kind: str
    path: str
    client_ref: str
    key: str | None
    deposit_cents: int
    expected_status: int

    def body(self) -> dict:
        return {"client_ref": self.client_ref, "session_id": "s-42", "dog_id": "d-7",
                "owner_id": "o-9", "deposit_cents": self.deposit_cents}

    def headers(self) -> dict[str, str]:
        return {"Idempotency-Key": self.key} if self.key else {}


def plan_tick(n: int, run_id: str) -> list[Request]:
    """The requests one stack receives on tick n, in order."""
    key = f"{REF_PREFIX}-{run_id}-{n}"
    tick = [Request("created", "/v2/bookings", key, key, DEPOSIT_CENTS, 201)]
    if n % REPLAY_EVERY == 0:
        tick.append(Request("replayed", "/v2/bookings", key, key, DEPOSIT_CENTS, 201))
    if n % CONFLICT_EVERY == 0:
        tick.append(Request("conflict", "/v2/bookings", key, key, CONFLICT_DEPOSIT_CENTS, 422))
    if n % MISSING_KEY_EVERY == 0:
        tick.append(Request("missing_key", "/v2/bookings", f"{key}-nokey", None, DEPOSIT_CENTS, 400))
    if n % NAIVE_EVERY == 0:
        tick.append(Request("naive", "/naive/bookings", f"{key}-naive", None, DEPOSIT_CENTS, 201))
    return tick


def ticks_for(minutes: float) -> int:
    return max(1, round(minutes * 60 / TICK_SECONDS))


def planned_counts(ticks: int) -> Counter[str]:
    """What one stack is sent over a run of this many ticks, by kind."""
    return Counter(request.kind for n in range(1, ticks + 1) for request in plan_tick(n, "plan"))


@dataclass
class StackResult:
    stack: str
    skipped: bool = False
    answered: Counter[str] = field(default_factory=Counter)    # kind -> got its expected status
    unexpected: Counter[str] = field(default_factory=Counter)  # "kind status" -> count
    failed: Counter[str] = field(default_factory=Counter)      # "kind ErrorName" -> count

    @property
    def ok(self) -> bool:
        return not self.unexpected and not self.failed

    def line(self) -> str:
        if self.skipped:
            return f"{self.stack:<7} skipped: no answer on /health (not running, or scaled to 0)"
        parts = [f"{kind} {self.answered[kind]}" for kind in KINDS]
        parts += [f"UNEXPECTED {what} x{n}" for what, n in sorted(self.unexpected.items())]
        parts += [f"FAILED {what} x{n}" for what, n in sorted(self.failed.items())]
        return f"{self.stack:<7} " + "  ".join(parts)


async def _load_stack(result: StackResult, ticks: int, run_id: str) -> None:
    async with httpx.AsyncClient(base_url=BASE_URLS[result.stack], timeout=10.0) as client:
        try:
            health = await client.get("/health", timeout=3.0)
        except httpx.HTTPError:
            health = None
        if health is None or health.status_code != 200:
            result.skipped = True
            return
        start = time.monotonic()
        for n in range(1, ticks + 1):
            for request in plan_tick(n, run_id):
                try:
                    response = await client.post(request.path, json=request.body(), headers=request.headers())
                except httpx.HTTPError as error:
                    result.failed[f"{request.kind} {type(error).__name__}"] += 1
                    continue
                if response.status_code == request.expected_status:
                    result.answered[request.kind] += 1
                else:
                    result.unexpected[f"{request.kind} {response.status_code}"] += 1
            # a fixed pace: tick n+1 starts n tick lengths after the first
            delay = start + n * TICK_SECONDS - time.monotonic()
            if n < ticks and delay > 0:
                await asyncio.sleep(delay)


def run(stacks: list[str] | tuple[str, ...], minutes: float,
        results: dict[str, StackResult] | None = None) -> dict[str, StackResult]:
    """Loads the given stacks concurrently. Pass `results` to keep the counts
    when the run is interrupted; it is filled in as requests are answered."""
    results = {} if results is None else results
    for stack in stacks:
        results[stack] = StackResult(stack)
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    ticks = ticks_for(minutes)

    async def load_all() -> None:
        await asyncio.gather(*(_load_stack(results[stack], ticks, run_id) for stack in stacks))

    asyncio.run(load_all())
    return results


def _report(results: dict[str, StackResult]) -> int:
    for result in results.values():
        print(f"observe-load: {result.line()}")
    running = [r for r in results.values() if not r.skipped]
    if not running:
        print("observe-load: no stack answered; run make up and make deploy first", file=sys.stderr)
        return 1
    return 0 if all(r.ok for r in running) else 1


def main() -> int:
    chosen = os.environ.get("STACK", "").strip()
    minutes_text = os.environ.get("MINUTES", "5").strip()
    try:
        minutes = float(minutes_text)
    except ValueError:
        minutes = 0.0
    if (chosen and chosen not in BASE_URLS) or minutes <= 0:
        print("usage: [STACK=<dotnet|java|python>] [MINUTES=<minutes, default 5>] python -m harness.observe_load",
              file=sys.stderr)
        return 2
    stacks = [chosen] if chosen else list(STACKS)
    print(f"observe-load: {ticks_for(minutes)} ticks of {TICK_SECONDS:g}s on {' '.join(stacks)}; "
          "Ctrl-C stops early")
    results: dict[str, StackResult] = {}
    try:
        run(stacks, minutes, results)
    except KeyboardInterrupt:
        print("observe-load: stopped early; counts so far")
    return _report(results)


if __name__ == "__main__":
    sys.exit(main())
