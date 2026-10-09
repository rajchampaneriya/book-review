from booking.application.ports.inbound import BookSessionCommand
from booking.application.services.request_hash import request_hash

# The spec's example body: sha256 of
# "r1-000123\ns-42\nd-7\no-9\n2500" in lowercase hex.
EXPECTED = "cc482c9f1d2adbf0044c34f9b74ff7666a763290e0cd5297b65d8e558317f582"


def command(**overrides):
    base = {"client_ref": "r1-000123", "session_id": "s-42", "dog_id": "d-7", "owner_id": "o-9", "deposit_cents": 2500}
    base.update(overrides)
    return BookSessionCommand(**base)


def test_known_vector():
    assert request_hash(command()) == EXPECTED


def test_is_64_lowercase_hex_chars():
    h = request_hash(command())
    assert len(h) == 64 and h == h.lower()
    int(h, 16)


def test_every_field_changes_the_hash():
    base = request_hash(command())
    variants = [
        command(client_ref="r1-000124"),
        command(session_id="s-43"),
        command(dog_id="d-8"),
        command(owner_id="o-10"),
        command(deposit_cents=2501),
    ]
    assert len({base, *(request_hash(c) for c in variants)}) == 6
