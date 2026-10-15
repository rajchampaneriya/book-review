"""Thin pytest-bdd step definitions for a subset of the new features.

Each step is one call into a driver (drivers.py), which delegates to the repo's code;
conftest.py puts that code on the import path. From the repo root:
  .venv/bin/python -m pytest -p no:cacheprovider -q bdd/steps
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from booking.application.ports.inbound import Created, InFlight
from conftest import REPO
from drivers import STACKS, BookingPolicy, Chart, MatrixHarness, Summary

FEATURES = Path(__file__).resolve().parents[1] / "features"


# ------------------------------------------------ exp3_idempotency_policy ---
@scenario(str(FEATURES / "exp3_idempotency_policy.feature"), "A fresh request key creates one booking and stores its result")
def test_fresh_key():
    pass


@scenario(str(FEATURES / "exp3_idempotency_policy.feature"), "A claimed request key with no stored result is reported as in flight")
def test_in_flight():
    pass


@scenario(str(FEATURES / "exp3_idempotency_policy.feature"), "A booking that fails part-way leaves no trace")
def test_partial_failure():
    pass


@scenario(str(FEATURES / "exp3_idempotency_policy.feature"), "A request key from a failed attempt can be used again")
def test_key_reusable_after_failure():
    pass


@pytest.fixture
def policy():
    return BookingPolicy()


@given(parsers.parse('no booking has been made with request key "{key}"'))
def no_booking(policy, key):
    assert policy.store.keys.get(key) is None


@given(parsers.parse('request key "{key}" is claimed for the same request but has no stored result'))
def claimed_without_result(policy, key):
    policy.claim_without_result(key)


@given("recording the deposit charge will fail once")
def charge_fails_once(policy):
    policy.fail_next_charge()


@given(parsers.parse('an earlier booking with request key "{key}" failed part-way'))
def earlier_failure(policy, key):
    policy.fail_next_charge()
    policy.book(key)


@when(parsers.parse('the service books with request key "{key}"'))
def book(policy, key):
    policy.book(key)


@then("the outcome is a new booking")
def outcome_created(policy):
    assert isinstance(policy.outcome, Created)


@then("the outcome is in flight")
def outcome_in_flight(policy):
    assert isinstance(policy.outcome, InFlight)


@then("the booking fails")
def booking_fails(policy):
    assert policy.error is not None


@then(parsers.parse("request key \"{key}\" stores that booking's confirmation and request fingerprint"))
def key_stores_result(policy, key):
    stored = policy.store.keys[key]
    assert stored.result["booking_id"] == policy.outcome.confirmation.booking_id
    assert stored.request_hash


@then("no booking or charge is recorded")
def nothing_recorded(policy):
    assert policy.ledger() == (0, 0)


@then(parsers.parse('no booking, no charge and no claim on request key "{key}" remain'))
def no_trace(policy, key):
    assert policy.ledger() == (0, 0)
    assert key not in policy.store.keys


@then(parsers.parse('exactly one booking and one deposit charge exist for request key "{key}"'))
def exactly_one(policy, key):
    assert policy.ledger() == (1, 1)


# ------------------------------------------------ exp3_measurement_run ------
@scenario(str(FEATURES / "exp3_measurement_run.feature"), "Only the stack under test serves traffic during its runs")
def test_only_stack_under_test_serves():
    pass


@pytest.fixture
def matrix():
    return MatrixHarness()


@given(parsers.parse("the matrix has finished measuring {earlier}"))
def matrix_finished(matrix, earlier):
    matrix.run()  # the whole matrix runs against fakes; each stack's start state is recorded


@when(parsers.parse("the matrix starts measuring {stack}"), target_fixture="started")
def matrix_starts(matrix, stack):
    return stack, matrix.at_first_run[stack]


@then(parsers.parse("{stack} has 1 replica"))
def under_test_serving(started, stack):
    _, state = started
    assert state[stack] == 1, f"{stack} had {state[stack]} replicas when its first measured run started"


@then("every other stack has 0 replicas")
def others_idle(started):
    stack, state = started
    assert all(state[s] == 0 for s in STACKS if s != stack)


# ------------------------------------------------ exp3_results_summary_and_chart
@scenario(str(FEATURES / "exp3_results_summary_and_chart.feature"),
          "Runs from other commits and shortened smoke runs are left out")
def test_summary_filters_runs():
    pass


@scenario(str(FEATURES / "exp3_results_summary_and_chart.feature"),
          "A group with no data is shown as missing, not as zero")
def test_chart_missing_group():
    pass


@pytest.fixture
def summary(tmp_path):
    return Summary(tmp_path)


@pytest.fixture
def chart(tmp_path):
    return Chart(REPO, tmp_path)


@given(parsers.parse("the run log holds 3 full-length runs of dotnet naive at 5% for commit {sha}"))
def three_full_runs(summary, sha):
    for run in ("1", "2", "3"):
        summary.add("dotnet", "naive", "0.05", run, 10000, 497, sha)


@given(parsers.parse("a 500-request smoke run of dotnet naive at 5% for commit {sha}"))
def smoke_run(summary, sha):
    summary.add("dotnet", "naive", "0.05", "9", 500, 25, sha)


@given(parsers.parse("1 full-length run of dotnet naive at 5% for commit {sha}"))
def other_commit_run(summary, sha):
    summary.add("dotnet", "naive", "0.05", "1", 10000, 0, sha)


@when(parsers.parse("the summary is built for commit {sha}"), target_fixture="groups")
def build_summary(summary, sha):
    return summary.build()  # today's exp3_summary has no commit filter; the step passes none


@then("the dotnet naive 5% group summarises exactly the 3 full-length runs")
def three_runs_only(groups):
    group = groups[("dotnet", "naive", "0.05")]
    assert group["runs"] == "3", f"summarised {group['runs']} runs"


@given(parsers.parse("a summary with no {stack} rows at a 1% fault rate"))
def summary_missing(chart, stack):
    chart.summary_without(stack, "0.01")


@when("the chart is drawn", target_fixture="svg")
def draw(chart):
    return chart.draw()


@then(parsers.parse('the {stack} 1% bars are labelled "no data"'))
def no_data_label(svg, stack):
    assert ">no data<" in svg, "missing groups are drawn as a 0 bar labelled 0"
