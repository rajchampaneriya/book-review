"""Contract test 1: /health returns the stack name."""

from conftest import STACK


def test_health_reports_the_stack(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "stack": STACK}
