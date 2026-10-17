"""Thin pytest-bdd step definitions for the platform features.

Each step is one call into a driver (drivers.py); the platform driver reads the
live k3d cluster through kubectl. From the repo root:
  .venv/bin/python -m pytest -p no:cacheprovider -q bdd/steps
"""
from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, scenario, then, when

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
