"""Contract test 7: an invalid body returns 400 invalid_request on both endpoints."""

import pytest

from conftest import booking_body

INVALID_BODIES = {
    "missing field": {k: v for k, v in booking_body("v").items() if k != "owner_id"},
    "unknown field": {**booking_body("v"), "extra": "no"},
    "negative deposit": booking_body("v", deposit_cents=-1),
    "zero deposit": booking_body("v", deposit_cents=0),
    "wrong type": {**booking_body("v"), "deposit_cents": "2500"},
}


@pytest.mark.parametrize("name", list(INVALID_BODIES))
@pytest.mark.parametrize("path", ["/naive/bookings", "/v2/bookings"])
def test_invalid_body_is_rejected(client, clean_schema, path, name):
    response = client.post(path, json=INVALID_BODIES[name], headers={"Idempotency-Key": "validation-1"})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}
