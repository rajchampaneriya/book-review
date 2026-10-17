"""Thin pytest-bdd step definitions for the platform features.

Each step is one call into a driver (drivers.py); the platform driver reads the
live k3d cluster through kubectl. From the repo root:
  .venv/bin/python -m pytest -p no:cacheprovider -q bdd/steps
"""
from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, parsers, scenario, then, when

from drivers import PlatformCluster

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


@when("the contract tests run against the python stack")
def run_contracts(cluster):
    cluster.contracts_passed = cluster.run_contract_tests("python")


@then("every contract test passes")
def contracts_passed(cluster):
    assert cluster.contracts_passed is True
