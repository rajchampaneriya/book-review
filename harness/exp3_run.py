"""One measured run: truncate, k6, count in the database, append runs.csv.

Usage (via make): STACK= VARIANT= FAULT= RUN= python -m harness.exp3_run
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness import db

REPO = Path(__file__).resolve().parents[1]
BASE_URLS = {"dotnet": "http://localhost:8081", "java": "http://localhost:8082", "python": "http://localhost:8083"}

COLUMNS = [
    "timestamp_utc", "stack", "variant", "fault_rate", "run", "rate",
    "logical_requests", "attempts", "timeouts", "gave_up", "dropped_iterations",
    "bookings_total", "duplicate_bookings", "duplicate_charges", "lost",
    "p50_ms", "p95_ms", "p99_ms", "git_sha",
]


def metric(summary: dict, name: str, field: str) -> int | float:
    return summary["metrics"].get(name, {}).get("values", {}).get(field, 0)


def main() -> int:
    stack = os.environ.get("STACK", "python")
    variant = os.environ.get("VARIANT", "")
    fault = os.environ.get("FAULT", "")
    run = os.environ.get("RUN", "")
    if stack not in BASE_URLS or variant not in ("naive", "v2") or not fault or not run:
        print("usage: STACK=<dotnet|java|python> VARIANT=<naive|v2> FAULT=<0|0.01|0.05> RUN=<n> python -m harness.exp3_run", file=sys.stderr)
        return 2

    run_id = f"{stack}-{variant}-f{fault}-r{run}"
    raw_path = REPO / "results" / "exp3" / "raw" / f"{stack}_{variant}_f{fault}_r{run}.json"

    print(f"exp3: truncating schema '{stack}'")
    db.truncate(stack)

    print(f"exp3: running k6 ({variant}, fault {fault}, run {run})")
    env = {
        **os.environ,
        "BASE_URL": BASE_URLS[stack],
        "STACK": stack,
        "VARIANT": variant,
        "FAULT_RATE": fault,
        "RUN_ID": run_id,
        "RUN": run,
    }
    subprocess.run(["k6", "run", "harness/k6/exp3.js"], check=True, cwd=REPO, env=env)

    summary = json.loads(raw_path.read_text(encoding="utf-8"))
    counts = db.counts(stack)

    logical = int(metric(summary, "logical_requests", "count"))
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stack": stack,
        "variant": variant,
        "fault_rate": fault,
        "run": run,
        "rate": int(env.get("RATE", "100") or "100"),
        "logical_requests": logical,
        "attempts": int(metric(summary, "attempts", "count")),
        "timeouts": int(metric(summary, "timeouts", "count")),
        "gave_up": int(metric(summary, "gave_up", "count")),
        "dropped_iterations": int(metric(summary, "dropped_iterations", "count")),
        "bookings_total": counts["bookings_total"],
        "duplicate_bookings": counts["duplicate_bookings"],
        "duplicate_charges": counts["duplicate_charges"],
        "lost": logical - counts["bookings_distinct"],
        "p50_ms": round(float(metric(summary, "successful_attempt_duration", "med"))),
        "p95_ms": round(float(metric(summary, "successful_attempt_duration", "p(95)"))),
        "p99_ms": round(float(metric(summary, "successful_attempt_duration", "p(99)"))),
        "git_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=REPO
        ).stdout.strip(),
    }

    out = REPO / "results" / "exp3" / "runs.csv"
    new_file = not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    print(f"exp3: appended {out.name}: duplicates={row['duplicate_bookings']} lost={row['lost']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
