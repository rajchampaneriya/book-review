"""Domain-level drivers used by the step definitions.

Step definitions stay thin: each one is a single call into a driver below, and the
drivers delegate to the repo's own code (the application service, harness/exp3_matrix,
harness/exp3_summary, figures/exp3_duplicates). Nothing here re-implements policy.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

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
        self.events: list[tuple] = []

    def run(self) -> None:
        m = self.matrix
        m.git_sha = lambda: "test-sha"
        m.completed_runs = lambda sha: set()
        m.hostinfo.write = lambda: None
        m.scale = lambda stack, n: self.replicas.__setitem__(stack, n)
        m.warm_up = lambda stack: None
        m.set_duplicate_audit_suspended = (
            lambda suspended: self.events.append(("audit", suspended)))

        def measured(stack, variant, fault, run):
            self.at_first_run.setdefault(stack, dict(self.replicas))
            self.events.append(("measured", stack))

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


class SchemaAudit(PlatformCluster):
    """Drives the schema-apply Job and the duplicate-audit CronJob (platform
    plan section 3.1) on the live cluster, reading the database back through
    harness.db the way the measured runs do."""

    REPO = Path(__file__).resolve().parents[2]
    TABLES = ("bookings", "charges", "idempotency_keys")

    def __init__(self) -> None:
        super().__init__()
        self.job_succeeded = False
        self.audit_log = ""
        self.rows_before: dict[tuple[str, str], int] = {}

    def postgres_serving(self) -> bool:
        out = subprocess.run(
            ["kubectl", "get", "deploy", "postgres", "-n", self.NS, "-o",
             "jsonpath={.status.availableReplicas}"],
            capture_output=True, text=True, check=False)
        return out.returncode == 0 and out.stdout.strip() not in ("", "0")

    def apply_schemas(self) -> None:
        subprocess.run(["bash", "infra/scripts/apply-schema.sh"], cwd=self.REPO,
                       check=True, capture_output=True)
        out = subprocess.run(
            ["kubectl", "get", "job", "schema-apply", "-n", self.NS, "-o",
             "jsonpath={.status.succeeded}"],
            capture_output=True, text=True, check=True)
        self.job_succeeded = out.stdout.strip() == "1"

    def tables_per_schema(self) -> dict[str, int]:
        from harness import db
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT table_schema, count(*) FROM information_schema.tables "
                        "WHERE table_schema IN ('dotnet','java','python') GROUP BY table_schema")
            counts = dict(cur.fetchall())
        conn.close()
        return counts

    def row_counts(self) -> dict[tuple[str, str], int]:
        from harness import db
        counts: dict[tuple[str, str], int] = {}
        with db.connect() as conn, conn.cursor() as cur:
            for schema in STACKS:
                for table in self.TABLES:
                    cur.execute(f"SELECT count(*) FROM {schema}.{table}")
                    counts[(schema, table)] = cur.fetchone()[0]
        conn.close()
        return counts

    def seed_python_duplicates(self, at_teardown) -> None:
        """Two bookings and two charges sharing one client_ref: exactly one
        duplicate for the audit to report. Truncated again at teardown."""
        from harness import db
        at_teardown(lambda: db.truncate("python"))
        db.truncate("python")
        ref = "audit-bdd"
        with db.connect() as conn, conn.cursor() as cur:
            for _ in range(2):
                cur.execute(
                    "INSERT INTO python.bookings (id, client_ref, session_id, dog_id, owner_id, "
                    "deposit_cents) VALUES (gen_random_uuid(), %s, 's-42', 'd-7', 'o-9', 2500) "
                    "RETURNING id", (ref,))
                cur.execute(
                    "INSERT INTO python.charges (id, booking_id, client_ref, amount_cents) "
                    "VALUES (gen_random_uuid(), %s, %s, 2500)", (cur.fetchone()[0], ref))
        conn.close()
        self.rows_before = self.row_counts()

    def trigger_audit(self) -> None:
        subprocess.run(["kubectl", "delete", "job", "duplicate-audit-bdd", "-n", self.NS],
                       capture_output=True, check=False)
        subprocess.run(["kubectl", "create", "job", "duplicate-audit-bdd", "-n", self.NS,
                        "--from=cronjob/duplicate-audit"], check=True, capture_output=True)
        subprocess.run(["kubectl", "wait", "--for=condition=complete",
                        "job/duplicate-audit-bdd", "-n", self.NS, "--timeout=120s"],
                       check=True, capture_output=True)
        out = subprocess.run(["kubectl", "logs", "job/duplicate-audit-bdd", "-n", self.NS],
                             capture_output=True, text=True, check=True)
        self.audit_log = out.stdout

    def reported_duplicates(self, stack: str) -> int | None:
        match = re.search(rf"{stack}\s*\|\s*(\d+)", self.audit_log)
        return int(match.group(1)) if match else None


class StackTelemetry(PlatformCluster):
    """Drives the observability overlay for the step 5 scenarios.

    Switches a stack's telemetry the way the repo does (make observe-up turns it
    on, infra/k8s/<stack>.yaml turns it off), books through the stack's NodePort
    like the contract tests, and reads traces and metrics back from lgtm through
    Grafana's data source proxy on localhost:8091.
    """

    REPO = Path(__file__).resolve().parents[2]
    GRAFANA = "http://localhost:8091"
    BASE_URLS = {"dotnet": "http://localhost:8081", "java": "http://localhost:8082",
                 "python": "http://localhost:8083"}
    # Spans leave the stacks every 5 s and metrics every 15 s (observe-up.sh);
    # the collectors batch on top. Wait well past both before giving up.
    WAIT_SECONDS = 120
    # How long a stack with telemetry off must stay silent in Tempo.
    QUIET_SECONDS = 30
    DASHBOARD = REPO / "infra" / "observability" / "dashboards" / "wcf-physics-overview.json"

    def __init__(self, stack: str = "python") -> None:
        super().__init__()
        self.stack = stack
        self.since_ns = 0
        self.trace_spans: list[dict] = []
        self.outcomes_before: dict[str, float] = {}

    # -- overlay state --------------------------------------------------------
    def overlay_installed(self) -> bool:
        out = subprocess.run(
            ["kubectl", "get", "deploy", "lgtm", "-n", self.NS, "-o",
             "jsonpath={.status.availableReplicas}"],
            capture_output=True, text=True, check=False)
        return out.returncode == 0 and out.stdout.strip() not in ("", "0")

    def telemetry_setting(self) -> str:
        out = subprocess.run(
            ["kubectl", "get", "deploy", self.stack, "-n", self.NS, "-o",
             "jsonpath={.spec.template.spec.containers[0].env[?(@.name=='OTEL_SDK_DISABLED')].value}"],
            capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def ensure_telemetry_on(self) -> None:
        """make observe-up's switch, run only when this stack's telemetry is off."""
        assert self.overlay_installed(), "lgtm is not running: run make observe-up first"
        if self.telemetry_setting() != "false":
            subprocess.run(["bash", "infra/scripts/observe-up.sh"], cwd=self.REPO,
                           check=True, capture_output=True)
        self._rollout()

    def apply_stack_manifest(self, at_teardown) -> None:
        """The Deployment exactly as make up applies it: telemetry off. If the
        overlay had it on, make observe-up switches it back on at teardown."""
        if self.overlay_installed() and self.telemetry_setting() == "false":
            at_teardown(lambda: subprocess.run(["bash", "infra/scripts/observe-up.sh"],
                                               cwd=self.REPO, check=True, capture_output=True))
        subprocess.run(["kubectl", "apply", "-f", f"infra/k8s/{self.stack}.yaml"],
                       cwd=self.REPO, check=True, capture_output=True)
        self._rollout()
        self.since_ns = time.time_ns()

    def _rollout(self) -> None:
        subprocess.run(["kubectl", "rollout", "status", f"deploy/{self.stack}", "-n", self.NS,
                        "--timeout=180s"], check=True, capture_output=True)

    # -- actions ------------------------------------------------------------
    def book_and_find_trace(self) -> None:
        assert self.book_with_key() == [201]
        self.wait_for_booking_trace()

    def book_twice(self) -> None:
        self.record_outcomes()
        assert self.book_with_key(times=2) == [201, 201]

    def book_with_key(self, times: int = 1) -> list[int]:
        key = f"otel-{self.stack}-{uuid.uuid4().hex[:12]}"
        body = {"client_ref": key, "session_id": "s-42", "dog_id": "d-7", "owner_id": "o-9",
                "deposit_cents": 2500}
        self.since_ns = time.time_ns()
        with httpx.Client(base_url=self.BASE_URLS[self.stack], timeout=10.0) as client:
            return [client.post("/v2/bookings", json=body, headers={"Idempotency-Key": key}).status_code
                    for _ in range(times)]

    def scale_to_zero(self, at_teardown) -> None:
        """What the matrix does to a stack that is not under test; one replica
        again at teardown."""
        at_teardown(self._restore_one_replica)
        self._scale(0)

    def _scale(self, replicas: int) -> None:
        subprocess.run(["bash", "infra/scripts/scale.sh", self.stack, str(replicas)],
                       cwd=self.REPO, check=True, capture_output=True)

    def _restore_one_replica(self) -> None:
        self._scale(1)
        self._rollout()

    # -- reads from lgtm ----------------------------------------------------
    def _grafana(self, path: str, **params) -> dict:
        response = httpx.get(f"{self.GRAFANA}{path}", params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()

    def _traces_since(self, traceql: str) -> list[dict]:
        found = self._grafana("/api/datasources/proxy/uid/tempo/api/search", q=traceql, limit=20,
                              start=self.since_ns // 1_000_000_000 - 5, end=int(time.time()) + 5)
        # two seconds of slack for clock skew between the host and the k3d node
        return [t for t in found.get("traces", [])
                if int(t["startTimeUnixNano"]) >= self.since_ns - 2_000_000_000]

    def wait_for_booking_trace(self) -> None:
        query = '{resource.service.name="%s" && span.http.route="/v2/bookings"}' % self.stack
        deadline = time.time() + self.WAIT_SECONDS
        while time.time() < deadline:
            traces = self._traces_since(query)
            if traces:
                self.trace_spans = self._spans(self._grafana(
                    f"/api/datasources/proxy/uid/tempo/api/traces/{traces[0]['traceID']}"))
                return
            time.sleep(5)
        self.trace_spans = []

    @staticmethod
    def _spans(trace: dict) -> list[dict]:
        spans = []
        for batch in trace.get("batches") or trace.get("resourceSpans") or []:
            for scope in batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []:
                for span in scope.get("spans", []):
                    attrs = {a["key"]: next(iter(a["value"].values()), None) for a in span.get("attributes", [])}
                    spans.append({"name": span["name"], "kind": str(span.get("kind", "")),
                                  "start": int(span["startTimeUnixNano"]), "end": int(span["endTimeUnixNano"]),
                                  "attributes": attrs})
        return spans

    def server_spans(self) -> list[dict]:
        return [s for s in self.trace_spans
                if "SERVER" in s["kind"] and s["attributes"].get("http.route") == "/v2/bookings"]

    def database_spans_inside_request(self) -> list[dict]:
        server = self.server_spans()
        if len(server) != 1:
            return []
        start, end = server[0]["start"], server[0]["end"]
        return [s for s in self.trace_spans
                if "postgresql" in (s["attributes"].get("db.system"), s["attributes"].get("db.system.name"))
                and start <= s["start"] and s["end"] <= end]

    def _prometheus(self, expr: str) -> list[dict]:
        found = self._grafana("/api/datasources/proxy/uid/prometheus/api/v1/query", query=expr)
        return found["data"]["result"]

    def outcome_total(self, outcome: str) -> float:
        result = self._prometheus(
            'sum(booking_outcomes_total{service_name="%s", outcome="%s"})' % (self.stack, outcome))
        return float(result[0]["value"][1]) if result else 0.0

    def record_outcomes(self) -> None:
        self.outcomes_before = {o: self.outcome_total(o) for o in ("created", "replayed")}

    def wait_for_outcome_increase(self, outcome: str) -> float:
        deadline = time.time() + self.WAIT_SECONDS
        increase = 0.0
        while time.time() < deadline:
            increase = self.outcome_total(outcome) - self.outcomes_before.get(outcome, 0.0)
            if increase >= 1:
                return increase
            time.sleep(5)
        return increase

    def ready_replicas_on_panel(self) -> float | None:
        """Runs the dashboard's own ready-replicas query and reads this stack's series."""
        dashboard = json.loads(self.DASHBOARD.read_text(encoding="utf-8"))
        panel = next(p for p in dashboard["panels"] if p["title"].startswith("Ready replicas"))
        expr = panel["targets"][0]["expr"]
        deadline = time.time() + self.WAIT_SECONDS
        value = None
        while time.time() < deadline:
            series = [r for r in self._prometheus(expr)
                      if r["metric"].get("k8s_deployment_name") == self.stack]
            value = float(series[0]["value"][1]) if series else None
            if value == 0:
                return value
            time.sleep(5)
        return value

    def exports_nothing(self) -> bool:
        if self.telemetry_setting() != "true":
            return False
        if not self.overlay_installed():
            return True
        time.sleep(self.QUIET_SECONDS)
        return not self._traces_since('{resource.service.name="%s"}' % self.stack)



class LoadPlan:
    """The fixed mix make observe-load sends, read from harness/observe_load.py
    without a cluster."""

    def __init__(self, minutes: float) -> None:
        self.minutes = minutes
        self.planned: dict[str, int] = {}

    def plan(self) -> None:
        from harness import observe_load
        self.planned = dict(observe_load.planned_counts(observe_load.ticks_for(self.minutes)))

    def counts(self, *kinds: str) -> tuple[int, ...]:
        return tuple(self.planned.get(kind, 0) for kind in kinds)


class ObserveLoad(StackTelemetry):
    """Drives make observe-load (harness/observe_load.py) against every stack and
    reads the dashboard back with the panels' own queries, as
    ready_replicas_on_panel does, so a broken panel query fails here too."""

    # Grafana picks $__rate_interval per panel; two minutes covers a 90-second
    # load plus the 15 s metric export and the collectors' batching.
    RATE_INTERVAL = "2m"
    # Longer than the 15 s metric export interval set by observe-up.sh: two
    # equal readings this far apart mean nothing is still on its way.
    COUNTER_SETTLE_SECONDS = 20
    OUTCOMES = ("created", "replayed", "conflict")

    def __init__(self, stack: str = "python") -> None:
        super().__init__(stack)
        self.results: dict = {}
        self.counters_before: dict[tuple[str, str], float] = {}

    # -- set-up and the load --------------------------------------------------
    def ensure_every_stack_on(self) -> None:
        for stack in STACKS:
            StackTelemetry(stack).ensure_telemetry_on()

    def scale_to_zero_and_wait(self, at_teardown) -> None:
        """The matrix's scale-down, then wait until the NodePort stops answering
        (scale.sh returns before the pod has gone)."""
        self.scale_to_zero(at_teardown)
        deadline = time.time() + self.WAIT_SECONDS
        while time.time() < deadline:
            try:
                httpx.get(f"{self.BASE_URLS[self.stack]}/health", timeout=3.0)
            except httpx.HTTPError:
                return
            time.sleep(2)
        raise AssertionError(f"{self.stack} still answers /health after scaling to 0")

    def run_load(self, seconds: int) -> None:
        from harness import observe_load
        self.results = observe_load.run(STACKS, seconds / 60)

    # -- what the load reported -----------------------------------------------
    def skipped_stacks(self) -> list[str]:
        return sorted(stack for stack, result in self.results.items() if result.skipped)

    def answered_everything(self, stacks: list[str]) -> bool:
        return all(not self.results[s].skipped and self.results[s].ok and self.results[s].answered["created"] > 0
                   for s in stacks)

    def sent_outcomes(self) -> dict[str, dict[str, int]]:
        return {stack: {outcome: result.answered[outcome] for outcome in self.OUTCOMES}
                for stack, result in self.results.items()}

    # -- the outcome counters -------------------------------------------------
    def _outcome_counters(self) -> dict[tuple[str, str], float]:
        rows = self._prometheus("sum by (service_name, outcome) (booking_outcomes_total)")
        return {(r["metric"].get("service_name", ""), r["metric"].get("outcome", "")): float(r["value"][1])
                for r in rows}

    def settle_outcome_counters(self) -> None:
        before = self._outcome_counters()
        deadline = time.time() + self.WAIT_SECONDS
        while time.time() < deadline:
            time.sleep(self.COUNTER_SETTLE_SECONDS)
            now = self._outcome_counters()
            if now == before:
                break
            before = now
        self.counters_before = before

    def outcome_increases(self) -> dict[str, dict[str, int]]:
        """Polls until every stack's counters rose by what the load sent, or the
        wait runs out; returns the increases either way."""
        expected = self.sent_outcomes()
        deadline = time.time() + self.WAIT_SECONDS
        while True:
            now = self._outcome_counters()
            increases = {stack: {o: round(now.get((stack, o), 0.0) - self.counters_before.get((stack, o), 0.0))
                                 for o in self.OUTCOMES}
                         for stack in expected}
            if increases == expected or time.time() > deadline:
                return increases
            time.sleep(5)

    # -- the dashboard's panels -----------------------------------------------
    def _panel_expr(self, title_prefix: str, expr_prefix: str = "") -> str:
        dashboard = json.loads(self.DASHBOARD.read_text(encoding="utf-8"))
        panel = next(p for p in dashboard["panels"] if p["title"].startswith(title_prefix))
        expr = next(t["expr"] for t in panel["targets"] if t["expr"].startswith(expr_prefix))
        return expr.replace("$__rate_interval", self.RATE_INTERVAL)

    def _missing_from_panel(self, expr: str, wanted: list[dict[str, str]]) -> list[dict[str, str]]:
        """Polls the panel's query until every wanted series shows a positive
        value; returns the ones still missing."""
        deadline = time.time() + self.WAIT_SECONDS
        while True:
            shown = [r["metric"] for r in self._prometheus(expr) if float(r["value"][1]) > 0]
            missing = [w for w in wanted if not any(all(m.get(k) == v for k, v in w.items()) for m in shown)]
            if not missing or time.time() > deadline:
                return missing
            time.sleep(5)

    def requests_panel_missing(self) -> list[dict[str, str]]:
        return self._missing_from_panel(
            self._panel_expr("Requests per second by stack and route"),
            [{"service_name": s, "http_route": r} for s in STACKS for r in ("/v2/bookings", "/naive/bookings")])

    def errors_panel_missing(self) -> list[dict[str, str]]:
        return self._missing_from_panel(
            self._panel_expr("4xx and 5xx responses per second"),
            [{"service_name": s, "http_response_status_code": c} for s in STACKS for c in ("422", "400")])

    def latency_p95_missing(self) -> list[dict[str, str]]:
        return self._missing_from_panel(
            self._panel_expr("Latency p50 / p95 / p99 per stack", "histogram_quantile(0.95"),
            [{"service_name": s} for s in STACKS])
