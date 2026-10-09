"""Contract test 2: the baseline is naive - two identical POSTs create two bookings."""

from conftest import booking_body, counts


def test_two_identical_posts_create_two_bookings_and_charges(client, db, clean_schema):
    first = client.post("/naive/bookings", json=booking_body("naive-dup"))
    second = client.post("/naive/bookings", json=booking_body("naive-dup"))

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["booking_id"] != second.json()["booking_id"]

    c = counts(db, clean_schema)
    assert c["bookings_total"] == 2
    assert c["charges_total"] == 2
    assert c["duplicate_bookings"] == 1
    assert c["duplicate_charges"] == 1
