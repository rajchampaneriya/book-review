"""Domain-level drivers used by the step definitions.

Step definitions stay thin: each one is a single call into a driver below, and the
drivers delegate to the repo's own code (the application service, harness/exp3_matrix,
harness/exp3_summary, figures/exp3_duplicates). Nothing here re-implements policy.
"""
from __future__ import annotations

import asyncio
import csv
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from booking.application.ports.inbound import BookSessionCommand
from booking.application.ports.outbound import StoredKey
from booking.application.services.book_session_idempotent import BookSessionIdempotentService
from booking.application.services.request_hash import request_hash
from fakes import InMemoryBookingStore  # stacks/python/tests/unit/fakes.py

STACKS = ["dotnet", "java", "python"]


class ChargeFailureStore(InMemoryBookingStore):
    """The repo's in-memory store, plus a switch that makes the next add_charge fail."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_next_charge = False

    @asynccontextmanager
    async def transaction(self):
        async with super().transaction() as tx:
            if self.fail_next_charge:
                self.fail_next_charge = False

                async def unavailable(charge):
                    raise RuntimeError("the charge could not be recorded")

                tx.add_charge = unavailable
            yield tx


class BookingPolicy:
    """Drives BookSessionIdempotentService through its driving port."""

    def __init__(self) -> None:
        self.store = ChargeFailureStore()
        self.service = BookSessionIdempotentService(self.store)
        self.command = BookSessionCommand("r1-000123", "s-42", "d-7", "o-9", 2500)
        self.outcome = None
        self.error: Exception | None = None

    def claim_without_result(self, key: str) -> None:
        self.store.keys[key] = StoredKey(key, request_hash(self.command), None)

    def fail_next_charge(self) -> None:
        self.store.fail_next_charge = True

    def book(self, key: str) -> None:
        self.outcome, self.error = None, None
        try:
            self.outcome = asyncio.run(self.service.book(key, self.command))
        except Exception as e:  # the failure path is an observable outcome here
            self.error = e

    def ledger(self) -> tuple[int, int]:
        return len(self.store.bookings), len(self.store.charges)


class MatrixHarness:
    """Runs harness.exp3_matrix.main() with kubectl, k6 and the per-run harness replaced by fakes,
    recording how many replicas each stack had when its first measured run started."""

    def __init__(self) -> None:
        import harness.exp3_matrix as matrix

        self.matrix = matrix
        self.replicas = {s: 1 for s in STACKS}
        self.at_first_run: dict[str, dict[str, int]] = {}

    def run(self) -> None:
        m = self.matrix
        m.git_sha = lambda: "test-sha"
        m.completed_runs = lambda sha: set()
        m.hostinfo.write = lambda: None
        m.scale = lambda stack, n: self.replicas.__setitem__(stack, n)
        m.warm_up = lambda stack: None

        def measured(stack, variant, fault, run):
            self.at_first_run.setdefault(stack, dict(self.replicas))

        m.measured_run = measured
        m.main()


class Summary:
    """Builds summary.csv with harness.exp3_summary from a run log written into tmp_path."""

    COLUMNS = ["timestamp_utc", "stack", "variant", "fault_rate", "run", "rate", "logical_requests", "attempts",
               "timeouts", "gave_up", "dropped_iterations", "bookings_total", "duplicate_bookings",
               "duplicate_charges", "lost", "p50_ms", "p95_ms", "p99_ms", "git_sha"]

    def __init__(self, tmp: Path) -> None:
        self.runs, self.out, self.rows = tmp / "runs.csv", tmp / "summary.csv", []

    def add(self, stack, variant, fault, run, logical, duplicates, sha):
        self.rows.append({"timestamp_utc": "2026-10-10T00:00:00+00:00", "stack": stack, "variant": variant,
                          "fault_rate": fault, "run": run, "rate": 100, "logical_requests": logical,
                          "attempts": logical, "timeouts": 0, "gave_up": 0, "dropped_iterations": 0,
                          "bookings_total": logical + duplicates, "duplicate_bookings": duplicates,
                          "duplicate_charges": duplicates, "lost": 0, "p50_ms": 1, "p95_ms": 3, "p99_ms": 8,
                          "git_sha": sha})

    def build(self) -> dict[tuple[str, str, str], dict[str, str]]:
        import harness.exp3_summary as summary

        with self.runs.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.COLUMNS)
            w.writeheader()
            w.writerows(self.rows)
        summary.RUNS, summary.OUT, summary.REPO = self.runs, self.out, self.out.parent
        summary.main()
        with self.out.open() as f:
            return {(r["stack"], r["variant"], r["fault_rate"]): r for r in csv.DictReader(f)}


class Chart:
    """Draws the chart with figures/exp3_duplicates.py as a subprocess, like the repo's own test."""

    def __init__(self, repo: Path, tmp: Path) -> None:
        self.script = repo / "figures" / "exp3_duplicates.py"
        self.fixture = repo / "figures" / "tests" / "fixtures" / "exp3_summary_synthetic.csv"
        self.input = tmp / "summary.csv"
        self.output = tmp / "chart.svg"

    def summary_without(self, stack: str, fault: str) -> None:
        with self.fixture.open() as f:
            rows = [r for r in csv.DictReader(f) if not (r["stack"] == stack and r["fault_rate"] == fault)]
        with self.input.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    def draw(self) -> str:
        subprocess.run([sys.executable, str(self.script), "--input", str(self.input), "--output",
                        str(self.output)], check=True, capture_output=True)
        return self.output.read_text(encoding="utf-8")


class PlatformCluster:
    """Reads the live k3d cluster through kubectl for the platform scenarios."""

    NS = "wcf-physics"
    # kube-router takes a few seconds to sync policy rules for a brand-new
    # pod; a probe that connects immediately is denied by lag, not by policy.
    SETTLE_SECONDS = 5

    def __init__(self) -> None:
        self.last_permission: bool | None = None
        self.connection_accepted: bool | None = None
        self.contracts_passed: bool | None = None

    def default_deny_applied(self) -> bool:
        out = subprocess.run(
            ["kubectl", "get", "networkpolicy", "default-deny", "-n", self.NS],
            capture_output=True, text=True, check=False,
        )
        return out.returncode == 0

    def reaches_postgres(self, client: str) -> bool:
        """Runs a throwaway pod labelled as <client> and reports whether it
        can open a TCP connection to postgres on 5432."""
        pod = f"netprobe-{client}"
        subprocess.run(["kubectl", "delete", "pod", pod, "-n", self.NS],
                       capture_output=True, check=False)
        subprocess.run(
            ["kubectl", "run", pod, "-n", self.NS, "--image=postgres:18.6",
             "--restart=Never", f"--labels=wcf-physics.io/identity={client}",
             "--command", "--", "sh", "-c",
             f"sleep {self.SETTLE_SECONDS}; pg_isready -h postgres -p 5432 -t 5"],
            check=True, capture_output=True)
        subprocess.run(
            ["kubectl", "wait", "--for=jsonpath={.status.phase}=Succeeded",
             f"pod/{pod}", "-n", self.NS, "--timeout=90s"],
            capture_output=True, check=False)
        out = subprocess.run(
            ["kubectl", "get", "pod", pod, "-n", self.NS, "-o",
             "jsonpath={.status.containerStatuses[0].state.terminated.exitCode}"],
            capture_output=True, text=True, check=True)
        subprocess.run(["kubectl", "delete", "pod", pod, "-n", self.NS],
                       capture_output=True, check=False)
        return out.stdout.strip() == "0"

    def run_contract_tests(self, stack: str) -> bool:
        repo = Path(__file__).resolve().parents[2]
        env = {**os.environ, "STACK": stack}
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "-c", "contracts/pytest.ini",
             "contracts/tests"],
            capture_output=True, text=True, cwd=repo, env=env, check=False,
        )
        return out.returncode == 0

    def deployment_service_account(self, deployment: str) -> str:
        out = subprocess.run(
            ["kubectl", "get", "deploy", deployment, "-n", self.NS, "-o",
             "jsonpath={.spec.template.spec.serviceAccountName}"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()

    def check_list_pods(self) -> None:
        # kubectl auth can-i exits 1 when the answer is no; the stdout text is the answer.
        out = subprocess.run(
            ["kubectl", "auth", "can-i", "list", "pods", "-n", self.NS,
             "--as", f"system:serviceaccount:{self.NS}:python"],
            capture_output=True, text=True, check=False,
        )
        self.last_permission = out.stdout.strip().lower() == "yes"

    def api_token_mounted(self) -> bool:
        out = subprocess.run(
            ["kubectl", "get", "pods", "-n", self.NS, "-l", "app.kubernetes.io/name=python",
             "-o", "jsonpath={range .items[*]}{.spec.containers[0].volumeMounts[*].mountPath} {end}"],
            capture_output=True, text=True, check=True,
        )
        return "secrets/kubernetes.io/serviceaccount" in out.stdout
