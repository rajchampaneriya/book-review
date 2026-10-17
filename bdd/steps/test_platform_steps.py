"""Thin pytest-bdd step definitions for the platform features.

Each step is one call into a driver (drivers.py); the platform driver reads the
live k3d cluster through kubectl. From the repo root:
  .venv/bin/python -m pytest -p no:cacheprovider -q bdd/steps
"""
from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, parsers, scenario, then, when

from drivers import LoadPlan, ObserveLoad, PlatformCluster, StackTelemetry

FEATURES = Path(__file__).resolve().parents[1] / "features"


# ------------------------------------------- platform_service_accounts ---
@scenario(str(FEATURES / "platform_service_accounts.feature"),
          "The python service cannot use the Kubernetes API")
def test_python_cannot_use_api():
    pass


@given("the python Deployment runs as the python service account", target_fixture="cluster")
def python_service_account():
    cluster = PlatformCluster()
    assert cluster.deployment_service_account("python") == "python"
    return cluster


@when("its permission to list pods in wcf-physics is checked")
def check_permission(cluster):
    cluster.check_list_pods()


@then("the permission is denied")
def permission_denied(cluster):
    assert cluster.last_permission is False


@then("the pod has no API token mounted")
def no_api_token(cluster):
    assert cluster.api_token_mounted() is False


# ------------------------------------------- platform_network_policy ---
@scenario(str(FEATURES / "platform_network_policy.feature"),
          "Only permitted connections reach the booking database")
def test_only_permitted_connections():
    pass


@scenario(str(FEATURES / "platform_network_policy.feature"),
          "The host still reaches the python stack through its NodePort")
def test_host_still_reaches_python():
    pass


@given("default-deny NetworkPolicy is applied in wcf-physics", target_fixture="cluster")
def default_deny_applied():
    cluster = PlatformCluster()
    assert cluster.default_deny_applied()
    return cluster


@when(parsers.parse("{client} opens a connection to postgres on port 5432"))
def open_connection(cluster, client):
    cluster.connection_accepted = cluster.reaches_postgres(client)


@then(parsers.parse("the connection is {result}"))
def connection_result(cluster, result):
    assert cluster.connection_accepted is (result == "accepted")


@when(parsers.parse("the contract tests run against the {stack} stack"))
def run_contracts(cluster, stack):
    cluster.contracts_passed = cluster.run_contract_tests(stack)


@then("every contract test passes")
def contracts_passed(cluster):
    assert cluster.contracts_passed is True


# ------------------------------------------- platform_observability ---
OBSERVABILITY = str(FEATURES / "platform_observability.feature")


@scenario(OBSERVABILITY, "A keyed booking leaves one trace with its database work")
def test_keyed_booking_leaves_one_trace():
    pass


@scenario(OBSERVABILITY, "The dashboard counts a replayed booking as a replay")
def test_dashboard_counts_a_replay():
    pass


@scenario(OBSERVABILITY, "The dashboard shows which stack is under test")
def test_dashboard_shows_stack_under_test():
    pass


@scenario(OBSERVABILITY, "Telemetry is off unless the overlay switches it on")
def test_telemetry_off_by_default():
    pass


@given(parsers.parse("the observability overlay is on for the {stack} stack"), target_fixture="cluster")
def overlay_on_for_stack(stack):
    cluster = StackTelemetry(stack)
    cluster.ensure_telemetry_on()
    return cluster


@given("the observability overlay is on", target_fixture="cluster")
def overlay_on():
    cluster = StackTelemetry("python")
    assert cluster.overlay_installed()
    return cluster


@given(parsers.parse("the {stack} Deployment from infra/k8s/{manifest}.yaml"), target_fixture="cluster")
def stack_as_make_up_applies_it(request, stack, manifest):
    cluster = StackTelemetry(stack)
    cluster.apply_stack_manifest(request.addfinalizer)
    return cluster


@when(parsers.parse("a client books a session with an idempotency key on the {stack} stack"))
def book_with_key(cluster, stack):
    cluster.book_and_find_trace()


@when(parsers.parse("a client sends the same keyed booking twice on the {stack} stack"))
def book_twice(cluster, stack):
    cluster.book_twice()


@when("the matrix scales python to 0 replicas")
def scale_python_to_zero(request, cluster):
    cluster.scale_to_zero(request.addfinalizer)


@then("one trace shows the HTTP request span")
def one_server_span(cluster):
    assert len(cluster.server_spans()) == 1, cluster.trace_spans


@then("the trace shows the database spans inside it")
def database_spans_inside(cluster):
    assert cluster.database_spans_inside_request(), cluster.trace_spans


@then(parsers.parse("the outcome counter shows one more {outcome} booking"))
def one_more_outcome(cluster, outcome):
    assert cluster.wait_for_outcome_increase(outcome) == 1


@then("the ready replicas panel shows python at 0")
def ready_replicas_zero(cluster):
    assert cluster.ready_replicas_on_panel() == 0


@then(parsers.parse("the {stack} pod exports no telemetry"))
def exports_no_telemetry(cluster, stack):
    assert cluster.exports_nothing()


# ---------------------------------------------- platform_observe_load ---
OBSERVE_LOAD = str(FEATURES / "platform_observe_load.feature")


@scenario(OBSERVE_LOAD, "The load sends a fixed mix of new, replayed, conflicting and naive bookings")
def test_load_mix_is_fixed():
    pass


@scenario(OBSERVE_LOAD, "A short load fills the request, error and latency panels for every stack")
def test_load_fills_application_panels():
    pass


@scenario(OBSERVE_LOAD, "The outcome counters rise by exactly what the load sent")
def test_outcome_counters_match_the_load():
    pass


@scenario(OBSERVE_LOAD, "The load skips a stack the matrix scaled to 0")
def test_load_skips_a_scaled_down_stack():
    pass


@given(parsers.parse("an observe-load run of {minutes:d} minutes"), target_fixture="plan")
def observe_load_run(minutes):
    return LoadPlan(minutes)


@when("the load is planned for one stack")
def plan_for_one_stack(plan):
    plan.plan()


@then(parsers.parse("it sends {created:d} new keyed bookings and {replayed:d} replays of them"))
def sends_keyed(plan, created, replayed):
    assert plan.counts("created", "replayed") == (created, replayed), plan.planned


@then(parsers.parse("it sends {conflict:d} conflicting bookings and {missing:d} bookings without a key"))
def sends_rejected(plan, conflict, missing):
    assert plan.counts("conflict", "missing_key") == (conflict, missing), plan.planned


@then(parsers.parse("it sends {naive:d} naive bookings"))
def sends_naive(plan, naive):
    assert plan.counts("naive") == (naive,), plan.planned


@given("the observability overlay is on for every stack", target_fixture="cluster")
def overlay_on_for_every_stack():
    cluster = ObserveLoad()
    cluster.ensure_every_stack_on()
    return cluster


@given("the outcome counters have settled")
def outcome_counters_settled(cluster):
    cluster.settle_outcome_counters()


@given("the matrix has scaled python to 0 replicas")
def python_scaled_to_zero(request, cluster):
    cluster.scale_to_zero_and_wait(request.addfinalizer)


@when(parsers.parse("the operator runs observe-load for {seconds:d} seconds"))
def run_observe_load(cluster, seconds):
    cluster.run_load(seconds)


@then("the requests panel shows keyed and naive bookings for every stack")
def requests_panel_filled(cluster):
    assert cluster.requests_panel_missing() == []


@then("the errors panel shows conflicts and missing keys for every stack")
def errors_panel_filled(cluster):
    assert cluster.errors_panel_missing() == []


@then("the latency panel shows a p95 for every stack")
def latency_panel_filled(cluster):
    assert cluster.latency_p95_missing() == []


@then("every stack's created, replayed and conflict counters rose by what the load sent")
def counters_match_the_load(cluster):
    assert cluster.outcome_increases() == cluster.sent_outcomes()


@then("the load reports python as skipped")
def python_skipped(cluster):
    assert cluster.skipped_stacks() == ["python"], cluster.results


@then("java and dotnet answered every booking the load sent")
def java_and_dotnet_answered(cluster):
    assert cluster.answered_everything(["java", "dotnet"]), cluster.results
