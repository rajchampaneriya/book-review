"""make exp3-all: warm-up per stack, then the full matrix in a fixed order.

STACKS x VARIANTS x FAULTS x RUNS; idle stacks are scaled to 0 replicas;
results/exp3/host.json is written once. Resumable: runs already present in
runs.csv for the same git SHA are skipped. DRY_RUN=1 prints the plan and the
estimated duration without running anything.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from harness import hostinfo

REPO = Path(__file__).resolve().parents[1]
STACKS = ["dotnet", "java", "python"]
VARIANTS = ["naive", "v2"]
FAULTS = ["0", "0.01", "0.05"]
RUNS = ["1", "2", "3"]
RUN_SECONDS = int(os.environ.get("TOTAL", "10000")) // int(os.environ.get("RATE", "100"))
WARMUP_SECONDS = 60


def git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=REPO
    ).stdout.strip()


def completed_runs(sha: str) -> set[tuple[str, str, str, str]]:
    path = REPO / "results" / "exp3" / "runs.csv"
    done: set[tuple[str, str, str, str]] = set()
    if not path.exists():
        return done
    with path.open() as f:
        for row in csv.DictReader(f):
            if row["git_sha"] == sha:
                done.add((row["stack"], row["variant"], row["fault_rate"], row["run"]))
    return done


def kubectl(*args: str) -> None:
    subprocess.run(["kubectl", "-n", "wcf-physics", *args], check=True, cwd=REPO)


def scale(stack: str, replicas: int) -> None:
    kubectl("scale", f"deploy/{stack}", "--replicas", str(replicas))


def warm_up(stack: str) -> None:
    """60 s at RATE with FAULT_RATE=0, not measured: no runs.csv row, summary to a temp file."""
    print(f"matrix: warm-up {stack} ({WARMUP_SECONDS}s at RATE={os.environ.get('RATE', '100')}, not measured)")
    rate = os.environ.get("RATE", "100")
    env = {
        **os.environ,
        "BASE_URL": f"http://localhost:{ {'dotnet': 8081, 'java': 8082, 'python': 8083}[stack] }",
        "STACK": stack,
        "VARIANT": "v2",
        "FAULT_RATE": "0",
        "RUN_ID": f"warmup-{stack}",
        "RUN": "warmup",
        "SUMMARY_PATH": tempfile.mktemp(suffix=".json"),
    }
    subprocess.run(
        ["k6", "run", "--quiet", "harness/k6/exp3.js"],
        check=True, cwd=REPO, env=env,
    )


def measured_run(stack: str, variant: str, fault: str, run: str) -> None:
    env = {**os.environ, "STACK": stack, "VARIANT": variant, "FAULT": fault, "RUN": run}
    subprocess.run(
        [sys.executable, "-m", "harness.exp3_run"], check=True, cwd=REPO, env=env
    )


def main() -> int:
    dry = os.environ.get("DRY_RUN") == "1"
    sha = git_sha()
    done = completed_runs(sha)

    plan: list[tuple[str, str, str, str]] = []
    warmups: list[str] = []
    for stack in STACKS:
        stack_runs = [
            (stack, variant, fault, run)
            for variant in VARIANTS
            for fault in FAULTS
            for run in RUNS
            if (stack, variant, fault, run) not in done
        ]
        if not stack_runs:
            print(f"matrix: {stack}: every run for this git SHA is already in runs.csv, skipped")
            continue
        warmups.append(stack)
        plan.extend(stack_runs)

    estimate = len(warmups) * WARMUP_SECONDS + len(plan) * RUN_SECONDS
    print(f"matrix: {len(plan)} measured run(s), {len(warmups)} warm-up(s), "
          f"estimated {estimate // 60} min {estimate % 60} s at TOTAL/RATE defaults")
    for stack, variant, fault, run in plan:
        print(f"matrix: planned {stack} {variant} fault={fault} run={run}")

    if dry:
        print("matrix: DRY_RUN=1, nothing executed")
        return 0

    hostinfo.write()
    try:
        for stack in STACKS:
            if stack not in warmups:
                continue
            for other in STACKS:
                if other != stack:
                    scale(other, 0)
            warm_up(stack)
            for planned_stack, variant, fault, run in plan:
                if planned_stack != stack:
                    continue
                measured_run(stack, variant, fault, run)
    finally:
        for stack in STACKS:
            scale(stack, 1)
        print("matrix: all stacks restored to 1 replica")
    print(f"matrix: done ({len(plan)} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
