"""Contract test 8: the fault hook is off unless FAULT_INJECTION=enabled."""


def test_fault_header_is_ignored_when_injection_is_disabled(client, clean_schema):
    response = client.post(
        "/v2/bookings",
        json={
            "client_ref": "fault-off",
            "session_id": "s-42",
            "dog_id": "d-7",
            "owner_id": "o-9",
            "deposit_cents": 2500,
        },
        headers={"Idempotency-Key": "fault-off-1", "X-Fault": "hold-after-commit"},
    )
    assert response.status_code == 201
    assert response.elapsed.total_seconds() < 0.5
